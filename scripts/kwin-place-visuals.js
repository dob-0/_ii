const titleNeedle = readConfig('title', 'ii-VISUALS');
const outputName = readConfig('output', 'HDMI-A-1');
const useFullscreen = readConfig('fullscreen', 'true') === 'true';

function findOutput() {
    const outputs = workspace.outputs || [];
    if (outputs.length === 0) return null;
    for (let i = 0; i < outputs.length; i++) {
        if (outputs[i].name === outputName) return outputs[i];
    }
    if (outputs.length === 1) return outputs[0];
    return outputs.slice().sort((a, b) => a.geometry.x - b.geometry.x)[1];
}

function titleOf(window) {
    return String(window.caption || window.resourceName || window.resourceClass || '');
}

function place(window) {
    try {
        if (!window || titleOf(window).indexOf(titleNeedle) === -1) return;
        const output = findOutput();
        if (!output) return;
        window.fullScreen = false;
        window.output = output;
        window.frameGeometry = output.geometry;
        window.fullScreen = useFullscreen;
    } catch (e) {
    }
}

try {
    workspace.windowAdded.connect(place);
} catch (e) {
    try {
        workspace.clientAdded.connect(place);
    } catch (ignored) {
    }
}

try {
    const windows = workspace.windowList ? workspace.windowList() : workspace.stackingOrder;
    for (let i = 0; i < windows.length; i++) place(windows[i]);
} catch (e) {
}
