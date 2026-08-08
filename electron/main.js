const { app, BrowserWindow, dialog } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

const BACKEND_PORT = 8000
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`

let mainWindow = null
let backendProcess = null

function getBackendPath() {
  // 开发模式：使用本地 Python 启动
  const devPath = path.join(__dirname, '..', 'backend')
  const devEnv = path.join(devPath, '.venv')
  if (require('fs').existsSync(devEnv)) {
    return { exe: 'python', args: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)], cwd: devPath }
  }
  // 打包模式：使用 PyInstaller 打好的 exe
  const bundled = path.join(process.resourcesPath, 'backend', 'ai-workbench.exe')
  if (require('fs').existsSync(bundled)) {
    return { exe: bundled, args: [], cwd: path.dirname(bundled) }
  }
  // 开发模式（dist 目录下）：使用 PyInstaller 构建的 exe
  const localDist = path.join(__dirname, 'backend-dist', 'ai-workbench.exe')
  if (require('fs').existsSync(localDist)) {
    return { exe: localDist, args: [], cwd: path.join(__dirname, 'backend-dist') }
  }
  return null
}

function startBackend() {
  const config = getBackendPath()
  if (!config) {
    dialog.showErrorBox('启动失败', '找不到后端服务。请确保已安装 Python 依赖或运行打包版本。')
    app.quit()
    return
  }

  backendProcess = spawn(config.exe, config.args, {
    cwd: config.cwd,
    env: {
      ...process.env,
      WORKBENCH_PASSWORD: process.env.WORKBENCH_PASSWORD || 'demo1234',
      WORKBENCH_SESSION_SECRET: process.env.WORKBENCH_SESSION_SECRET || 'ai-workbench-electoron-secret-key-32chars',
      COOKIE_SECURE: 'false',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  backendProcess.stdout.on('data', (data) => {
    console.log('[backend]', data.toString().trim())
  })
  backendProcess.stderr.on('data', (data) => {
    console.log('[backend]', data.toString().trim())
  })
  backendProcess.on('exit', (code) => {
    console.log(`[backend] 进程退出，退出码 ${code}`)
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-status', 'down')
    }
  })
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    const check = (remaining) => {
      if (remaining <= 0) {
        reject(new Error('后端启动超时'))
        return
      }
      http.get(BACKEND_URL + '/api/auth/me', (res) => {
        resolve()
      }).on('error', () => {
        setTimeout(() => check(remaining - 1), 1000)
      })
    }
    check(retries)
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: '个人 AI 工作台',
    backgroundColor: '#f1eee5',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  mainWindow.setMenuBarVisibility(false)
  mainWindow.loadURL(BACKEND_URL)

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(async () => {
  startBackend()
  try {
    await waitForBackend()
  } catch (err) {
    dialog.showErrorBox('启动失败', err.message)
    app.quit()
    return
  }
  createWindow()
})

app.on('window-all-closed', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
  app.quit()
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
  }
})