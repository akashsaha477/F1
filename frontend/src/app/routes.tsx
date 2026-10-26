import type { ReactElement } from "react";
import OverviewPage from "../pages/Overview";
import DriverExplorerPage from "../pages/DriverExplorer";
import ExplainPredictionPage from "../pages/ExplainPrediction";

export const routes: { path: string; element: ReactElement }[] = [
  { path: "/", element: <OverviewPage /> },
  { path: "/drivers", element: <DriverExplorerPage /> },
  { path: "/explain", element: <ExplainPredictionPage /> },
];
