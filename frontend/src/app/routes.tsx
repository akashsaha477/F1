import type { ReactElement } from "react";
import OverviewPage from "../pages/Overview";
import DriverExplorerPage from "../pages/DriverExplorer";
import ExplainPredictionPage from "../pages/ExplainPrediction";
import DriverComparisonPage from "../pages/DriverComparison";

export const routes: { path: string; element: ReactElement }[] = [
  { path: "/", element: <OverviewPage /> },
  { path: "/drivers", element: <DriverExplorerPage /> },
  { path: "/compare", element: <DriverComparisonPage /> },
  { path: "/explain", element: <ExplainPredictionPage /> },
];
