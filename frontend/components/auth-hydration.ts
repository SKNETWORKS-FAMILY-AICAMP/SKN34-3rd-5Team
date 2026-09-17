"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};
const clientReady = () => true;
const serverReady = () => false;

// Credential forms must remain inert until their preventDefault handler is
// attached. Otherwise a fast submission can navigate with a native GET request.
export function useAuthHydrated() {
  return useSyncExternalStore(subscribe, clientReady, serverReady);
}
