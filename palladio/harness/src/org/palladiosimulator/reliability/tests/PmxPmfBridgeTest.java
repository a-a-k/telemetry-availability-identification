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
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.stream.Stream;

import org.eclipse.core.runtime.NullProgressMonitor;
import org.eclipse.emf.ecore.EStructuralFeature;
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

public class PmxPmfBridgeTest {

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
        final String scenarioId;
        final double success;
        final double failure;
        final double physicalMass;
        final long evaluatedStates;
        final long totalStates;

        ProbabilityResult(final MarkovTransformationResult result) {
            final EStructuralFeature nameFeature = result.getScenario().eClass()
                    .getEStructuralFeature("entityName");
            assertNotNull("PCM scenario must expose its entityName feature", nameFeature);
            final Object name = result.getScenario().eGet(nameFeature);
            assertTrue("PCM scenario entityName must be a string", name instanceof String);
            scenarioId = (String) name;
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
        config.setUsageModelFile(modelRoot.resolve("extracted.usagemodel").toUri().toString());
        config.setAllocationFiles(List.of(
                modelRoot.resolve("extracted.allocation").toUri().toString()));
        return config;
    }

    private static List<ProbabilityResult> solve(final Path modelRoot) throws Exception {
        final PCMSolverWorkflowRunConfiguration config = configuration(modelRoot);
        final ModelBuilder builder = new ModelBuilder(config);
        builder.execute(new NullProgressMonitor());
        final PCMInstance model = new PCMInstance((PCMResourceSetPartition) builder
                .blackboard().getPartition(LoadPCMModelsIntoBlackboardJob.PCM_MODELS_PARTITION_ID));
        assertTrue("The aligned-input PCM instance must be valid: " + modelRoot,
                model.isValid());
        final Pcm2MarkovStrategy solver = new Pcm2MarkovStrategy(config);
        solver.transform(model);
        assertNotNull(solver.getAllSolvedValues());
        assertFalse("Each aligned-input model must contain a scenario",
                solver.getAllSolvedValues().isEmpty());
        final List<ProbabilityResult> results = new ArrayList<>();
        for (final MarkovTransformationResult raw : solver.getAllSolvedValues()) {
            results.add(new ProbabilityResult(raw));
        }
        return results;
    }

    private static String requiredEnvironment(final String name) {
        final String value = System.getenv(name);
        assertNotNull(name + " must be defined", value);
        assertFalse(name + " must not be blank", value.isBlank());
        return value;
    }

    private static String jsonString(final String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
    }

    private static void assertModelFiles(final Path modelRoot) {
        assertTrue(Files.isRegularFile(modelRoot.resolve("extracted.repository")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("extracted.resourceenvironment")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("extracted.allocation")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("extracted.system")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("extracted.usagemodel")));
    }

    private static void assertPhysicalResult(final ProbabilityResult result,
            final double tolerance) {
        assertFalse("Scenario id must not be blank", result.scenarioId.isBlank());
        assertTrue(result.success >= 0.0 && result.success <= 1.0);
        assertTrue(result.failure >= 0.0 && result.failure <= 1.0);
        assertEquals(1.0, result.success + result.failure, tolerance);
        assertEquals(1.0, result.physicalMass, tolerance);
        assertEquals(result.totalStates, result.evaluatedStates);
    }


    private static String number(final double value) {
        return Double.isFinite(value) ? Double.toString(value) : jsonString(Double.toString(value));
    }

    @Test
    public void retainEveryNativeAndDisclosedBridgeAttempt() throws Exception {
        final Path root = Path.of(requiredEnvironment("TAID_PALLADIO_ALIGNED_ROOT")).toAbsolutePath();
        final Path output = Path.of(requiredEnvironment("TAID_PALLADIO_RESULT")).toAbsolutePath();
        final List<Path> models;
        try (Stream<Path> stream = Files.list(root)) {
            models = stream.filter(Files::isDirectory)
                    .sorted(Comparator.comparing(p -> p.getFileName().toString())).toList();
        }
        assertEquals(Integer.parseInt(requiredEnvironment("TAID_EXPECTED_MODEL_COUNT")), models.size());
        final List<String> records = new ArrayList<>();
        Files.createDirectories(output.getParent());
        for (int repetition = 0; repetition < 2; repetition++) {
            for (final Path model : models) {
                final String id = model.getFileName().toString();
                final long started = System.nanoTime();
                final String prefix = "{\"model_id\":" + jsonString(id)
                        + ",\"repetition\":" + repetition;
                String record;
                System.out.println("TAID_PMX_MODEL_START " + id + " pass=" + repetition);
                try {
                    assertModelFiles(model);
                    final List<ProbabilityResult> results = solve(model);
                    assertEquals(1, results.size());
                    final ProbabilityResult result = results.get(0);
                    record = prefix + ",\"status\":\"solved\",\"scenario_id\":" + jsonString(result.scenarioId)
                            + ",\"success_probability\":" + number(result.success)
                            + ",\"failure_probability_sum\":" + number(result.failure)
                            + ",\"physical_state_probability\":" + number(result.physicalMass)
                            + ",\"evaluated_physical_states\":" + result.evaluatedStates
                            + ",\"total_physical_states\":" + result.totalStates;
                } catch (Exception | AssertionError error) {
                    error.printStackTrace(System.err);
                    record = prefix + ",\"status\":\"error\",\"error_type\":"
                            + jsonString(error.getClass().getName()) + ",\"error_message\":"
                            + jsonString(String.valueOf(error.getMessage()));
                }
                record += ",\"load_solve_elapsed_nanoseconds\":" + (System.nanoTime() - started) + "}";
                records.add(record);
                Files.writeString(output, "{\"runs\":[\n" + String.join(",\n", records) + "\n]}\n",
                        StandardCharsets.UTF_8);
            }
        }
        assertEquals(2 * models.size(), records.size());
    }
}
