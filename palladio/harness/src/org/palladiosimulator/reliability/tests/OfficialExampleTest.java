package org.palladiosimulator.reliability.tests;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import org.eclipse.core.runtime.NullProgressMonitor;
import org.junit.Test;
import org.palladiosimulator.analyzer.workflow.core.ConstantsContainer;
import org.palladiosimulator.analyzer.workflow.core.blackboard.PCMResourceSetPartition;
import org.palladiosimulator.analyzer.workflow.core.jobs.LoadPCMModelsIntoBlackboardJob;
import org.palladiosimulator.analyzer.workflow.jobs.EventsTransformationJob;
import org.palladiosimulator.analyzer.workflow.jobs.LoadMiddlewareConfigurationIntoBlackboardJob;
import org.palladiosimulator.analyzer.workflow.jobs.ValidatePCMModelsJob;
import org.palladiosimulator.reliability.solver.pcm2markov.MarkovTransformationResult;
import org.palladiosimulator.reliability.solver.pcm2markov.Pcm2MarkovStrategy;
import org.palladiosimulator.solver.core.models.PCMInstance;
import org.palladiosimulator.solver.core.runconfig.PCMSolverWorkflowRunConfiguration;

import de.uka.ipd.sdq.workflow.jobs.ICompositeJob;
import de.uka.ipd.sdq.workflow.jobs.SequentialBlackboardInteractingJob;
import de.uka.ipd.sdq.workflow.mdsd.blackboard.MDSDBlackboard;

public class OfficialExampleTest {

    private static final class ModelBuilder
            extends SequentialBlackboardInteractingJob<MDSDBlackboard>
            implements ICompositeJob {

        private final MDSDBlackboard testBlackboard;

        ModelBuilder(final PCMSolverWorkflowRunConfiguration config) {
            super(false);
            testBlackboard = new MDSDBlackboard();
            myBlackboard = testBlackboard;
            addJob(new LoadPCMModelsIntoBlackboardJob(config));
            addJob(new LoadMiddlewareConfigurationIntoBlackboardJob(config));
            addJob(new ValidatePCMModelsJob(config));
            add(new EventsTransformationJob(config.getStoragePluginID(),
                    config.getEventMiddlewareFile(), false));
        }

        MDSDBlackboard blackboard() {
            return testBlackboard;
        }
    }

    private static final class ProbabilityResult {
        final double success;
        final double failure;
        final double physicalMass;
        final long evaluatedStates;
        final long totalStates;

        ProbabilityResult(final MarkovTransformationResult result) {
            success = result.getSuccessProbability();
            failure = result.getCumulatedFailureTypeProbabilities().values().stream()
                    .mapToDouble(Double::doubleValue).sum();
            physicalMass = result.getCumulatedPhysicalStateProbability();
            evaluatedStates = result.getPhysicalStateEvaluationCount();
            totalStates = result.getNumberOfPhysicalSystemStates();
        }
    }

    private static PCMSolverWorkflowRunConfiguration configuration(final Path modelRoot) {
        final PCMSolverWorkflowRunConfiguration config = new PCMSolverWorkflowRunConfiguration();
        config.setReliabilityAnalysis(true);
        config.setPrintMarkovStatistics(false);
        config.setPrintMarkovSingleResults(false);
        config.setSensitivityModelEnabled(false);
        config.setSensitivityModelFileName(null);
        config.setSensitivityLogFileName(null);
        config.setDeleteTemporaryDataAfterAnalysis(true);
        config.setDistance(1.0);
        config.setDomainSize(32);
        config.setIterationOverPhysicalSystemStatesEnabled(true);
        config.setMarkovModelReductionEnabled(true);
        config.setNumberOfEvaluatedSystemStatesEnabled(false);
        config.setNumberOfEvaluatedSystemStates(0);
        config.setNumberOfExactDecimalPlacesEnabled(false);
        config.setNumberOfExactDecimalPlaces(0);
        config.setSolvingTimeLimitEnabled(false);
        config.setMarkovModelStorageEnabled(false);
        config.setMarkovEvaluationMode("POINTSOFFAILURE");
        config.setSaveResultsToFileEnabled(false);
        config.setRMIMiddlewareFile(ConstantsContainer.DEFAULT_RMI_MIDDLEWARE_REPOSITORY_FILE);
        config.setEventMiddlewareFile(ConstantsContainer.DEFAULT_EVENT_MIDDLEWARE_FILE);
        config.setUsageModelFile(modelRoot.resolve("default.usagemodel").toUri().toString());
        config.setAllocationFiles(List.of(
                modelRoot.resolve("default.allocation").toUri().toString()));
        return config;
    }

    private static ProbabilityResult solve(final Path modelRoot) throws Exception {
        final PCMSolverWorkflowRunConfiguration config = configuration(modelRoot);
        final ModelBuilder builder = new ModelBuilder(config);
        builder.execute(new NullProgressMonitor());
        final PCMInstance model = new PCMInstance((PCMResourceSetPartition) builder
                .blackboard().getPartition(LoadPCMModelsIntoBlackboardJob.PCM_MODELS_PARTITION_ID));
        assertTrue("The official PCM instance must be valid", model.isValid());
        final Pcm2MarkovStrategy solver = new Pcm2MarkovStrategy(config);
        solver.transform(model);
        assertNotNull(solver.getAllSolvedValues());
        assertEquals(1, solver.getAllSolvedValues().size());
        return new ProbabilityResult(solver.getAllSolvedValues().get(0));
    }

    private static String requiredEnvironment(final String name) {
        final String value = System.getenv(name);
        assertNotNull(name + " must be defined", value);
        assertFalse(name + " must not be blank", value.isBlank());
        return value;
    }

    private static void writeResult(final Path output, final List<ProbabilityResult> results)
            throws IOException {
        final StringBuilder json = new StringBuilder();
        json.append("{\n  \"repetitions\": [\n");
        for (int index = 0; index < results.size(); index++) {
            final ProbabilityResult result = results.get(index);
            if (index > 0) {
                json.append(",\n");
            }
            json.append(String.format(Locale.ROOT,
                    "    {\"index\": %d, \"success_probability\": %.17g, "
                            + "\"failure_probability_sum\": %.17g, "
                            + "\"physical_state_probability\": %.17g, "
                            + "\"evaluated_physical_states\": %d, "
                            + "\"total_physical_states\": %d}",
                    index, result.success, result.failure, result.physicalMass,
                    result.evaluatedStates, result.totalStates));
        }
        json.append("\n  ]\n}\n");
        Files.createDirectories(output.getParent());
        Files.writeString(output, json.toString(), StandardCharsets.UTF_8);
    }

    @Test
    public void officialReliabilityExampleIsRepeatableAndConservesProbability()
            throws Exception {
        final Path modelRoot = Path.of(requiredEnvironment("TAID_OFFICIAL_EXAMPLE_DIR"))
                .toAbsolutePath().normalize();
        final Path output = Path.of(requiredEnvironment("TAID_PALLADIO_RESULT"))
                .toAbsolutePath().normalize();
        final int repeatRuns = Integer.parseInt(requiredEnvironment("TAID_REPEAT_RUNS"));
        final double tolerance = Double.parseDouble(
                requiredEnvironment("TAID_PROBABILITY_TOLERANCE"));
        final String expectedText = System.getenv("TAID_EXPECTED_SUCCESS_PROBABILITY");
        assertTrue(Files.isRegularFile(modelRoot.resolve("default.usagemodel")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("default.allocation")));
        assertTrue(repeatRuns >= 2);

        final List<ProbabilityResult> results = new ArrayList<>();
        for (int repetition = 0; repetition < repeatRuns; repetition++) {
            final ProbabilityResult result = solve(modelRoot);
            assertTrue(result.success >= 0.0 && result.success <= 1.0);
            assertTrue(result.failure >= 0.0 && result.failure <= 1.0);
            assertEquals(1.0, result.success + result.failure, tolerance);
            assertEquals(1.0, result.physicalMass, tolerance);
            assertEquals(result.totalStates, result.evaluatedStates);
            results.add(result);
        }
        for (int index = 1; index < results.size(); index++) {
            assertEquals(results.get(0).success, results.get(index).success, tolerance);
        }
        if (expectedText != null && !expectedText.isBlank()) {
            assertEquals(Double.parseDouble(expectedText), results.get(0).success,
                    tolerance);
        }
        writeResult(output, results);
    }
}
