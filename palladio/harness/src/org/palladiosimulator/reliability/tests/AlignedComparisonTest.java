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

public class AlignedComparisonTest {

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

    private static final class RunRecord {
        final String modelId;
        final int repetition;
        final ProbabilityResult result;
        final long loadSolveElapsedNanoseconds;

        RunRecord(final String modelId, final int repetition,
                final ProbabilityResult result,
                final long loadSolveElapsedNanoseconds) {
            this.modelId = modelId;
            this.repetition = repetition;
            this.result = result;
            this.loadSolveElapsedNanoseconds = loadSolveElapsedNanoseconds;
        }
    }

    private static final class WarmupRecord {
        final String modelId;
        final int scenarioCount;
        final long loadSolveElapsedNanoseconds;

        WarmupRecord(final String modelId, final int scenarioCount,
                final long loadSolveElapsedNanoseconds) {
            this.modelId = modelId;
            this.scenarioCount = scenarioCount;
            this.loadSolveElapsedNanoseconds = loadSolveElapsedNanoseconds;
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
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static void assertModelFiles(final Path modelRoot) {
        assertTrue(Files.isRegularFile(modelRoot.resolve("default.repository")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("default.resourceenvironment")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("default.allocation")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("default.system")));
        assertTrue(Files.isRegularFile(modelRoot.resolve("default.usagemodel")));
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

    private static void writeResult(final Path output, final WarmupRecord warmup,
            final List<RunRecord> runs) throws IOException {
        final StringBuilder json = new StringBuilder();
        json.append("{\n  \"warmup\": {");
        json.append(String.format(Locale.ROOT,
                "\"model_id\": %s, \"scenario_count\": %d, "
                        + "\"load_solve_elapsed_nanoseconds\": %d",
                jsonString(warmup.modelId), warmup.scenarioCount,
                warmup.loadSolveElapsedNanoseconds));
        json.append("},\n  \"runs\": [\n");
        for (int index = 0; index < runs.size(); index++) {
            final RunRecord run = runs.get(index);
            final ProbabilityResult result = run.result;
            if (index > 0) {
                json.append(",\n");
            }
            json.append(String.format(Locale.ROOT,
                    "    {\"model_id\": %s, \"scenario_id\": %s, "
                            + "\"repetition\": %d, "
                            + "\"success_probability\": %.17g, "
                            + "\"failure_probability_sum\": %.17g, "
                            + "\"physical_state_probability\": %.17g, "
                            + "\"evaluated_physical_states\": %d, "
                            + "\"total_physical_states\": %d, "
                            + "\"load_solve_elapsed_nanoseconds\": %d}",
                    jsonString(run.modelId), jsonString(result.scenarioId),
                    run.repetition, result.success, result.failure,
                    result.physicalMass, result.evaluatedStates,
                    result.totalStates, run.loadSolveElapsedNanoseconds));
        }
        json.append("\n  ]\n}\n");
        Files.createDirectories(output.getParent());
        Files.writeString(output, json.toString(), StandardCharsets.UTF_8);
    }

    @Test
    public void alignedComparisonIsRepeatableAndConservesProbability() throws Exception {
        final Path modelsRoot = Path.of(requiredEnvironment("TAID_PALLADIO_ALIGNED_ROOT"))
                .toAbsolutePath().normalize();
        final Path output = Path.of(requiredEnvironment("TAID_PALLADIO_RESULT"))
                .toAbsolutePath().normalize();
        final int repeatRuns = Integer.parseInt(requiredEnvironment("TAID_REPEAT_RUNS"));
        final int expectedModels = Integer.parseInt(
                requiredEnvironment("TAID_EXPECTED_MODEL_COUNT"));
        final int expectedCases = Integer.parseInt(
                requiredEnvironment("TAID_EXPECTED_CASE_COUNT"));
        final double tolerance = Double.parseDouble(
                requiredEnvironment("TAID_PROBABILITY_TOLERANCE"));
        assertTrue(Files.isDirectory(modelsRoot));
        assertEquals("M9D has exactly two measured solver passes", 2, repeatRuns);
        assertTrue("M9D requires a positive model count", expectedModels > 0);
        assertEquals("M9D has one scenario per model", expectedModels, expectedCases);
        assertTrue("Probability tolerance must be finite and nonnegative",
                Double.isFinite(tolerance) && tolerance >= 0.0);

        final List<Path> modelRoots;
        try (Stream<Path> stream = Files.list(modelsRoot)) {
            modelRoots = stream.filter(Files::isDirectory)
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .toList();
        }
        assertEquals(expectedModels, modelRoots.size());
        assertFalse("M9D requires at least one aligned-input model", modelRoots.isEmpty());
        for (final Path modelRoot : modelRoots) {
            assertModelFiles(modelRoot);
        }

        final Path warmupRoot = modelRoots.get(0);
        final String warmupModelId = warmupRoot.getFileName().toString();
        System.out.println("TAID_M9D_WARMUP_START model_id=" + warmupModelId);
        final long warmupStarted = System.nanoTime();
        final List<ProbabilityResult> warmupResults = solve(warmupRoot);
        final long warmupElapsed = System.nanoTime() - warmupStarted;
        assertEquals("The lexical warmup model must contain exactly one scenario",
                1, warmupResults.size());
        assertPhysicalResult(warmupResults.get(0), tolerance);
        final WarmupRecord warmup = new WarmupRecord(warmupModelId,
                warmupResults.size(), warmupElapsed);

        final List<RunRecord> runs = new ArrayList<>();
        final Map<String, ProbabilityResult> firstResults = new HashMap<>();
        int scenarioCount = 0;
        for (int repetition = 0; repetition < repeatRuns; repetition++) {
            for (final Path modelRoot : modelRoots) {
                final String modelId = modelRoot.getFileName().toString();
                System.out.println("TAID_M9D_MODEL_START model_id=" + modelId
                        + " repetition=" + repetition);
                final long started = System.nanoTime();
                final List<ProbabilityResult> results = solve(modelRoot);
                final long elapsed = System.nanoTime() - started;
                assertEquals("Each aligned-input model must contain exactly one scenario",
                        1, results.size());
                final ProbabilityResult result = results.get(0);
                assertPhysicalResult(result, tolerance);
                if (repetition == 0) {
                    assertFalse("Each model id must occur once per measured pass",
                            firstResults.containsKey(modelId));
                    firstResults.put(modelId, result);
                    scenarioCount += 1;
                } else {
                    final ProbabilityResult first = firstResults.get(modelId);
                    assertNotNull("Model missing from first measured pass", first);
                    assertEquals("Scenario changed between measured passes",
                            first.scenarioId, result.scenarioId);
                    assertEquals(first.success, result.success, tolerance);
                    assertEquals(first.failure, result.failure, tolerance);
                    assertEquals(first.physicalMass, result.physicalMass, tolerance);
                    assertEquals(first.evaluatedStates, result.evaluatedStates);
                    assertEquals(first.totalStates, result.totalStates);
                }
                runs.add(new RunRecord(modelId, repetition, result, elapsed));
            }
        }
        assertEquals(expectedCases, scenarioCount);
        assertEquals(expectedModels, firstResults.size());
        assertEquals(expectedCases * repeatRuns, runs.size());
        writeResult(output, warmup, runs);
    }
}
