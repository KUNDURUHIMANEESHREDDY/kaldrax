import { HashRouter } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import Kaldrax from "./pages/Kaldrax";
import "./styles/kaldrax.css";

export default function App() {
  return <ToastProvider><HashRouter><Kaldrax /></HashRouter></ToastProvider>;
}
