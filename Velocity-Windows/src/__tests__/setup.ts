import { vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

const createEmitter = () => ({
    on: vi.fn(),
    removeAllListeners: vi.fn(),
});

vi.mock('@tauri-apps/api/core', () => ({
    invoke: vi.fn(() => Promise.resolve()),
}));

// Mock all Tauri plugins before any component imports
vi.mock('@tauri-apps/plugin-shell', () => ({
    Command: {
        sidecar: vi.fn(() => ({
            on: vi.fn(),
            removeAllListeners: vi.fn(),
            stdout: createEmitter(),
            stderr: createEmitter(),
            spawn: vi.fn(() => Promise.resolve({ pid: 1234, kill: vi.fn() })),
        })),
        create: vi.fn(() => ({ execute: vi.fn() })),
    },
}));

vi.mock('@tauri-apps/plugin-opener', () => ({
    openPath: vi.fn(),
    openUrl: vi.fn(),
}));

vi.mock('@tauri-apps/plugin-updater', () => ({
    check: vi.fn(() => Promise.resolve(null)),
}));

vi.mock('@tauri-apps/plugin-process', () => ({
    relaunch: vi.fn(),
}));

vi.mock('@tauri-apps/plugin-autostart', () => ({
    enable: vi.fn(),
    disable: vi.fn(),
    isEnabled: vi.fn(() => Promise.resolve(false)),
}));

// Mock fetch to prevent real network requests
globalThis.fetch = vi.fn(() =>
    Promise.resolve({
        ok: false,
        json: () => Promise.resolve({}),
    } as Response)
);
