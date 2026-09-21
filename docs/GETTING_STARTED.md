# Getting Started with CollaBuild

## Quick Start (5 minutes)

### 1. Using Docker (Easiest)

```bash
git clone https://github.com/Ari-Han-t/collabuild.git
cd collabuild
docker-compose up
```

Then open http://localhost:5173

### 2. Manual Setup

**Backend:**
```bash
cd backend
npm install
cp .env.example .env
npm run db:migrate
npm run dev
```

**Frontend (new terminal):**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### 3. Create Account & Test

1. Go to http://localhost:5173
2. Click "Register"
3. Create a test account
4. Click "New Project"
5. Start drawing!

## Project Structure

```
collabuild/
├── backend/              # Express.js + Socket.io server
│   ├── src/
│   │   ├── controllers/  # Route handlers
│   │   ├── services/     # Business logic
│   │   ├── websocket/    # Real-time handlers
│   │   └── middleware/   # Auth & error handling
│   └── prisma/           # Database schema
├── frontend/             # React + TypeScript app
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page views
│   │   ├── store/        # Redux slices
│   │   └── canvas/       # Drawing engine
│   └── vite.config.ts    # Build config
└── docs/                 # Documentation
```

## Tech Stack

- **Frontend**: React 18, TypeScript, Canvas API, Tailwind CSS, Redux
- **Backend**: Node.js, Express, TypeScript, Socket.io
- **Database**: PostgreSQL, Redis
- **DevOps**: Docker, GitHub Actions

## Features

- ✅ Real-time collaboration
- ✅ Drawing shapes (rectangles, circles, lines)
- ✅ Project management
- ✅ User authentication
- ✅ Version history
- ✅ Comments & feedback
- ✅ Responsive design
- ✅ Dark mode ready

## Available Scripts

**Backend:**
- `npm run dev` - Start dev server
- `npm run build` - Build for production
- `npm run db:migrate` - Run migrations
- `npm run test` - Run tests

**Frontend:**
- `npm run dev` - Start Vite dev server
- `npm run build` - Build for production
- `npm run preview` - Preview build
- `npm run lint` - Run ESLint

## Environment Variables

See `.env.example` files in backend and frontend directories.

Key variables:
- `DATABASE_URL` - PostgreSQL connection
- `JWT_SECRET` - Secret for JWT tokens
- `CORS_ORIGIN` - Frontend URL
- `VITE_API_URL` - Backend API URL

## Database

PostgreSQL is used for persistence. Schema includes:
- Users & authentication
- Projects & workspaces
- Drawings & shapes
- Comments & collaboration
- Version history

## Security

- JWT-based authentication
- CORS protection
- Input validation
- Rate limiting
- Environment variable management
- SQL injection prevention (Prisma ORM)

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for:
- Docker deployment
- Railway setup
- AWS EC2 guide
- SSL certificate setup
- Database migration in production

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for:
- System design
- Real-time collaboration flow
- Scalability considerations
- Technology choices

## API Documentation

See [docs/API.md](docs/API.md) for:
- Authentication endpoints
- Project management endpoints
- WebSocket events
- Request/response examples

## Roadmap

- [ ] Freehand drawing tool
- [ ] Image uploads to canvas
- [ ] Text tool improvements
- [ ] Export to PNG/SVG
- [ ] Real-time presence awareness
- [ ] Advanced commenting with threads
- [ ] Keyboard shortcuts
- [ ] Mobile app
- [ ] OAuth integration
- [ ] Team workspaces

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Creative Commons Attribution 4.0 International License (CC BY 4.0) - see [LICENSE](LICENSE)

## Support

- GitHub Issues: Report bugs or request features
- Discussions: Ask questions and share ideas
- Email: Support requests

## Author

Built with ❤️ by Sai Karun Nandipati
