# NovaQ frontend

The NovaQ frontend is a React and TypeScript single-page application built with
Vite.

From this directory, install the locked dependencies and start the development
server:

```powershell
npm ci
npm run dev
```

The available quality and build commands are:

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

`npm run build` type-checks the project and creates the production assets in
`dist/`. The Docker image builds these assets from source. For API setup, Docker
usage, and repository-wide guidance, see the [root README](../README.md).
