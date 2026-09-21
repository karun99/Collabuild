# CollaBuild - Real-time Collaborative Design Platform

A modern, full-stack collaborative design and prototyping platform where teams can create, edit, and iterate together in real-time. Think of it as a simplified Figma with powerful real-time collaboration features, version history, and an intuitive canvas experience.

![CollaBuild](https://img.shields.io/badge/CollaBuild-v1.0-blue)
![License](https://img.shields.io/badge/license-CC%20BY%204.0-lightgrey)

## 🎯 Features

### Core Capabilities
- **🎨 Real-time Collaboration** - Multiple users drawing and designing simultaneously with live cursor tracking
- **🛠️ Rich Canvas Tools** - Rectangles, circles, lines, text, image uploads, freehand drawing, with layer management
- **👥 Workspace & Projects** - Organize designs, invite team members, manage permissions
- **💬 Comments & Mentions** - Real-time commenting with @mentions and resolution tracking
- **⏮️ Version History** - Full undo/redo with persistent version snapshots
- **📤 Export Options** - Download as PNG, SVG, or PDF
- **🎭 Dark Mode** - Beautiful dark and light theme support
- **🔐 Authentication** - Secure JWT-based authentication with OAuth ready
- **📊 Activity Dashboard** - View recent projects, activity feed, collaboration metrics

## 🏗️ Technology Stack

### Frontend
- **React 18** with TypeScript
- **Canvas API** for rendering
- **Redux Toolkit** for state management
- **Tailwind CSS** for styling
- **Socket.io Client** for real-time updates
- **Vite** for fast development

### Backend
- **Node.js** with Express
- **TypeScript** for type safety
- **Socket.io** for WebSocket communication
- **PostgreSQL** for data persistence
- **Prisma ORM** for database management
- **JWT** for authentication
- **Redis** for caching and pub/sub

### DevOps & Deployment
- **Docker** for containerization (multi-stage, dev + runtime targets)
- **Docker Compose** for both development and one-command production
- **Nginx** serves the SPA and proxies `/api` + WebSocket (single origin)
- **GitHub Actions** for CI/CD and versioned image publishing to GHCR
- **AWS/Railway/Vercel** ready (see docs)

## 🚀 Quick Start

### Option A — Docker Compose (Recommended, easiest)

```bash
git clone https://github.com/karun99/collabuild-1.git
cd collabuild

# Production: one command brings up everything behind a single nginx entry point
docker compose -f docker-compose.prod.yml up -d --build
# Open http://localhost:8080

# Development (hot-reload)
docker compose up --build
# Frontend http://localhost:5173 · Backend http://localhost:3000
```

### Option B — Manual Setup

**Prerequisites:** Node.js 18+ · PostgreSQL 14+ (optional, mock DB is default)

1. **Backend**
```bash
cd backend
npm install
cp .env.example .env
npm run dev          # or: npm run build && npm start
```

2. **Frontend**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev          # or: npm run build && npm run preview
```

3. **Access the application**
- Frontend (dev): http://localhost:5173
- Backend API (dev): http://localhost:3000
- Production (single origin): http://localhost:8080

> Everything runs out of the box with an in-memory mock database — no setup
> required. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production + PaaS,
> [SECURITY.md](SECURITY.md) for the security/versioning policy.

## 🔖 Versioning

This project uses [Semantic Versioning](https://semver.org/). Every dependency
security/version update is **version-controlled** via Dependabot PRs, committed
lockfiles, and SemVer release tags. See
[SECURITY.md](SECURITY.md#version-control-for-every-update) and
[CHANGELOG.md](CHANGELOG.md).

## 📁 Project Structure

```
collabuild/
├── backend/                 # Node.js Express server
│   ├── src/
│   │   ├── controllers/     # Route handlers
│   │   ├── middleware/      # Auth & error handling
│   │   ├── websocket/       # Socket.io handlers
│   │   ├── utils/           # Utilities
│   │   └── index.ts         # Entry point
│   ├── prisma/              # Database schema
│   ├── .env.example         # Environment template
│   └── Dockerfile           # Multi-stage (dev + runtime)
├── frontend/                # React application
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── store/           # Redux store
│   │   ├── types/           # TypeScript types
│   │   ├── services/        # API services
│   │   ├── canvas/          # Canvas rendering
│   │   └── App.tsx          # Main component
│   ├── nginx.conf           # Production proxy config
│   └── Dockerfile
├── docs/                    # Documentation
├── .github/
│   ├── workflows/           # CI, image publish, deploy
│   └── dependabot.yml       # Security + version updates
├── docker-compose.yml       # Development
├── docker-compose.prod.yml  # Production (one-command deploy)
├── .env.prod.example
├── SECURITY.md              # Security & versioning policy
├── CHANGELOG.md
├── VERSION
└── README.md
```

## 🔑 Key Features Deep Dive

### Real-time Collaboration
- WebSocket connections using Socket.io
- Live cursor positions with user avatars
- Conflict-free collaborative editing (CRDT principles)
- Presence awareness (who's online, viewing what)

### Canvas System
- Efficient rendering with requestAnimationFrame
- Layer management with depth ordering
- Transform tools (move, resize, rotate)
- Grid and snap-to-grid support
- Zoom and pan functionality

### State Management
- Redux for client-side state
- Optimistic updates for smooth UX
- Conflict resolution for simultaneous edits
- Offline support with sync on reconnect

### Database
- Normalized schema for scalability
- Indexed queries for performance
- Audit logging for history
- Soft deletes for data retention

## 📚 API Documentation

### Authentication
```
POST /api/auth/register      - Create new account
POST /api/auth/login         - Login with credentials
POST /api/auth/refresh       - Refresh JWT token
POST /api/auth/logout        - Logout
```

### Projects
```
GET    /api/projects         - List user's projects
POST   /api/projects         - Create new project
GET    /api/projects/:id     - Get project details
PUT    /api/projects/:id     - Update project
DELETE /api/projects/:id     - Delete project
```

### Collaboration
```
WebSocket events (Socket.io):
- drawing:update             - Send canvas updates
- drawing:delete             - Delete object
- cursor:move                - Broadcast cursor position
- comment:add                - Add comment
- version:create             - Create version snapshot
```

## 🛠️ Development

### Available Scripts

**Backend:**
```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run db:migrate   # Run database migrations
npm run db:seed      # Seed database
npm run test         # Run tests
```

**Frontend:**
```bash
npm run dev          # Start dev server
npm run build        # Build for production
npm run preview      # Preview production build
npm run lint         # Run ESLint
npm run type-check   # TypeScript check
```

## 🔒 Security Features

- JWT-based authentication
- CORS protection
- Rate limiting
- SQL injection prevention (Prisma ORM)
- XSS protection
- CSRF tokens
- Input validation and sanitization
- Environment variable management

## 📦 Deployment

### Single-Node Production (Recommended)
```bash
cp .env.prod.example .env     # set JWT_SECRET etc.
docker compose -f docker-compose.prod.yml up -d --build
```

### Environment Variables

**Backend (.env)**
```
NODE_ENV=production
DATABASE_URL=postgresql://...
JWT_SECRET=your-secret-key
REDIS_URL=redis://...
CORS_ORIGIN=https://yourdomain.com
```

**Frontend (.env / build args)**
```
VITE_API_URL=https://api.yourdomain.com
VITE_WS_URL=wss://api.yourdomain.com
```

### Deploy to Railway, Vercel, AWS, or a VPS
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions,
including the GitHub Actions deploy workflow and versioned GHCR images.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0) — see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

Built with ❤️ by [Sai Karun Nandipati](https://github.com/karun99)

## 📞 Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Version:** 1.0.0  
**Last Updated:** January 2026
