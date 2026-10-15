module.exports = {
  packagerConfig: {
    // Validate cached Electron archives against the pinned package's official hashes.
    download: { checksums: require('electron/checksums.json') },
    asar: true,
    executableName: 'KriptoTerminali',
    icon: './assets/icon.ico',
    extraResource: ['./engine-dist/kripto-engine'],
    ignore: [/^\/.venv/, /^\/local-ai/, /^\/engine/, /^\/tests/, /^\/scripts/, /^\/src/, /^\/artifacts/, /^\/build/, /^\/out/, /^\/node_modules\/playwright/, /^\/node_modules\/typescript/, /\.spec$/],
    win32metadata: { CompanyName: 'Kripto Terminali', FileDescription: 'Kripto Terminali', ProductName: 'Kripto Terminali' }
  },
  makers: [
    { name: '@electron-forge/maker-squirrel', config: { name: 'KriptoTerminali', setupExe: 'KriptoTerminali-Kurulum.exe', setupIcon: './assets/icon.ico', noMsi: true } },
    { name: '@electron-forge/maker-zip', platforms: ['win32'] }
  ]
};
