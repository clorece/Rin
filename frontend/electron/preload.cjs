const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    sendMessage: (message) => ipcRenderer.send('message', message),
    resizeWindow: (dimensions) => ipcRenderer.send('resize-window', dimensions),
    quitApp: () => ipcRenderer.send('quit-app'),
    getSystemIdleTime: () => ipcRenderer.invoke('get-system-idle-time'),

});
