// Bridges the renderer to the one thing only Electron can do: a native
// folder-picker (#70). `contextBridge`, not raw `ipcRenderer` exposure, per
// `electron/main.mjs`'s own comment about how the IPC boundary is meant to
// be crossed.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("libellusHost", {
  openWorkingDirectory: () => ipcRenderer.invoke("workdir:open"),
});
