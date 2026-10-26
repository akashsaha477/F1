import type { ReactElement } from "react";
import OverviewPage from "../pages/Overview";
import DriverExplorerPage from "../pages/DriverExplorer";
import ExplainPredictionPage from "../pages/ExplainPrediction";
import DriverComparisonPage from "../pages/DriverComparison";
import TrackExplorerPage from "../pages/TrackExplorer";
import TyreWeatherLabPage from "../pages/TyreWeatherLab";
import RaceExplorerPage from "../pages/RaceExplorer";
import ScenarioLabPage from "../pages/ScenarioLab";
import MethodologyPage from "../pages/Methodology";

export const routes: { path: string; element: ReactElement }[] = [
  { path: "/", element: <OverviewPage /> },
  { path: "/drivers", element: <DriverExplorerPage /> },
  { path: "/compare", element: <DriverComparisonPage /> },
  { path: "/tracks", element: <TrackExplorerPage /> },
  { path: "/tyres-weather", element: <TyreWeatherLabPage /> },
  { path: "/races", element: <RaceExplorerPage /> },
  { path: "/explain", element: <ExplainPredictionPage /> },
  { path: "/scenarios", element: <ScenarioLabPage /> },
  { path: "/methodology", element: <MethodologyPage /> },
];
