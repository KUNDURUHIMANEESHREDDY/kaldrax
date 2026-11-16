import { createContext } from "react";
import type { StoreApi } from "./AppStore";

export const StoreContext = createContext<StoreApi | null>(null);
