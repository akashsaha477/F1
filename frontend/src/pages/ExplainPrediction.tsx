import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useLapPrediction } from "../api/hooks";
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui";
import { DriverSelect, ScenarioForm, defaultScenario, scenarioPayload, type ScenarioState } from "../components/ScenarioForm";
import { PredictionView } from "../components/PredictionView";

export default function ExplainPredictionPage() {
  const [params] = useSearchParams();
  const [driver, setDriver] = useState(params.get("driver") ?? "");
  const [scenario, setScenario] = useState<ScenarioState>({ ...defaultScenario, event_id: params.get("event") ?? "" });
  const mutation = useLapPrediction();
  const ready = driver && (scenario.mode === "next" || scenario.event_id);

  return (
    <div className="space-y-5">
      <PageHeader title="Explain a prediction"
        description="Predict a driver's representative race-lap pace for a stated scenario and inspect why the model predicts it, how uncertain it is, and which observations support it." />
      <Card title="Scenario">
        <ScenarioForm value={scenario} onChange={setScenario}>
          <DriverSelect season={scenario.mode === "event" ? scenario.season : undefined} value={driver} onChange={setDriver} label="Driver" />
        </ScenarioForm>
        <div className="mt-4 flex items-center gap-3">
          <Button disabled={!ready || mutation.isPending} onClick={() => mutation.mutate({ driver_id: driver, ...scenarioPayload(scenario) })}>
            {mutation.isPending ? "Predicting…" : "Predict and explain"}
          </Button>
          {!ready && <span className="text-xs text-ink-muted">Choose a driver and a race (or switch to “next race”).</span>}
        </div>
      </Card>
      {mutation.isPending && <LoadingState label="Running model and explanation…" />}
      {mutation.error && <ErrorState error={mutation.error} />}
      {mutation.data && <PredictionView p={mutation.data} />}
      {!mutation.data && !mutation.isPending && !mutation.error && <EmptyState>No prediction yet.</EmptyState>}
    </div>
  );
}
