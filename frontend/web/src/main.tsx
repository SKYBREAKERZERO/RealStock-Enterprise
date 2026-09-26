import { StrictMode } from "react";

import {
  createRoot,
} from "react-dom/client";

import {
  QueryClientProvider,
} from "@tanstack/react-query";

import {
  BrowserRouter,
} from "react-router-dom";

import App from "./App";

import {
  queryClient,
} from "./api/queryClient";

import "./i18n";

import "./styles.css";


const rootElement =
  document.getElementById(
    "root",
  );

if (!rootElement) {
  throw new Error(
    "Root element was not found",
  );
}


createRoot(
  rootElement,
).render(
  <StrictMode>
    <QueryClientProvider
      client={
        queryClient
      }
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);