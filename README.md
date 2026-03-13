# 🚀 ContentPro.fr

Plateforme de génération de contenu IA avec Content Studio.

## 📋 Stack Technique

- **Next.js 16** - App Router
- **React 19** - UI Framework
- **TypeScript 5** - Type Safety
- **Tailwind CSS 4** - Styling
- **shadcn/ui** - UI Components
- **Prisma** - ORM
- **Supabase** - PostgreSQL Database
- **NextAuth.js** - Authentication
- **z-ai-web-dev-sdk** - AI Integration
- **PM2** - Process Manager

## 🛠️ Développement Local

```bash
# Installer les dépendances
bun install

# Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs

# Générer le client Prisma
bun run db:generate

# Lancer en développement
bun run dev
```

Ouvrir [http://localhost:3000](http://localhost:3000)

## 🏗️ Build Production

```bash
bun run build
bun start
```

## 🚀 Déploiement

Le déploiement est automatisé via GitHub Actions:

1. **Push sur main/master** → Déploiement automatique
2. **Workflow manual** → Via GitHub Actions UI

### Prérequis VPS

- Node.js 20+
- PM2 (`npm install -g pm2`)
- Apache avec mod_proxy

### Variables GitHub Secrets

| Secret | Description |
|--------|-------------|
| `VPS_HOST` | IP du serveur |
| `VPS_USER` | Utilisateur SSH |
| `VPS_SSH_KEY` | Clé SSH privée |
| `VPS_PORT` | Port SSH (22) |
| `DATABASE_URL` | Connection string Supabase |
| `NEXTAUTH_SECRET` | Secret NextAuth |
| `NEXTAUTH_URL` | URL de production |

## 📁 Structure

```
src/
├── app/              # Next.js App Router
│   ├── api/          # API Routes
│   ├── page.tsx      # Page d'accueil
│   ├── layout.tsx    # Layout principal
│   └── globals.css   # Styles globaux
├── components/       # Composants React
│   └── ui/           # shadcn/ui components
├── hooks/            # Custom React hooks
└── lib/              # Utilitaires & configs
```

## 🔐 Variables d'Environnement

Voir `.env.example` pour la liste complète.

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `NEXT_PUBLIC_SUPABASE_URL` | URL Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Clé publique Supabase |
| `NEXTAUTH_SECRET` | Secret pour NextAuth |
| `NEXTAUTH_URL` | URL de l'application |

## 📊 Base de Données

```bash
# Pousser le schema
bun run db:push

# Créer une migration
bun run db:migrate

# Reset la base
bun run db:reset
```

## 🔄 CI/CD

Le pipeline GitHub Actions:

1. **Build** - Compilation et tests
2. **Deploy** - Déploiement sur VPS
3. **Notify** - Notification du status

## 📝 License

MIT © ContentPro.fr
