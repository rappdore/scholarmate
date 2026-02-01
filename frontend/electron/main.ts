import { app, BrowserWindow, shell } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

// Declare the magic constants that electron-forge plugin-vite injects
declare const MAIN_WINDOW_VITE_DEV_SERVER_URL: string | undefined;
declare const MAIN_WINDOW_VITE_NAME: string | undefined;

// Backend process reference
let backendProcess: ChildProcess | null = null;

function startBackend(): void {
  // Path to backend directory (relative to the frontend directory)
  const backendDir = path.join(__dirname, '../../../backend');

  console.log('Starting backend server...');

  // Spawn the backend using uv
  backendProcess = spawn('uv', ['run', 'uvicorn', 'main:app', '--reload'], {
    cwd: backendDir,
    stdio: 'inherit', // Show backend output in terminal
    detached: true, // Create new process group for clean shutdown
  });

  backendProcess.on('error', err => {
    console.error('Failed to start backend:', err);
  });

  backendProcess.on('exit', code => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
  });
}

function stopBackend(): void {
  if (backendProcess) {
    console.log('Stopping backend server...');
    // On macOS/Linux, we need to kill the process group
    if (process.platform !== 'win32') {
      process.kill(-backendProcess.pid!, 'SIGTERM');
    } else {
      backendProcess.kill('SIGTERM');
    }
    backendProcess = null;
  }
}

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: 'hiddenInset', // Nice macOS style
    trafficLightPosition: { x: 15, y: 15 },
    show: false, // Don't show until ready
  });

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    // In development, load from Vite dev server
    mainWindow.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else if (MAIN_WINDOW_VITE_NAME) {
    // In production, load the built files
    mainWindow.loadFile(
      path.join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`)
    );
  }
}

// This method will be called when Electron has finished initialization
app.whenReady().then(() => {
  // Set dock icon on macOS (for dev mode)
  if (process.platform === 'darwin' && app.dock) {
    const iconPath = path.join(__dirname, '../../assets/icon.png');
    app.dock.setIcon(iconPath);
  }

  // Start the backend server
  startBackend();

  // Give backend a moment to start, then create window
  setTimeout(createWindow, 1500);

  // On macOS, re-create window when dock icon is clicked and no windows exist
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed (including macOS for this app)
app.on('window-all-closed', () => {
  app.quit();
});

// Clean up backend when app is quitting
app.on('will-quit', () => {
  stopBackend();
});

// Handle process termination signals
process.on('SIGINT', () => {
  stopBackend();
  app.quit();
});

process.on('SIGTERM', () => {
  stopBackend();
  app.quit();
});
