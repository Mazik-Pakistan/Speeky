from prisma import Prisma

# ponytail: named `db` not `prisma` — the pip package itself is called `prisma`,
# so a module-level `prisma = Prisma()` here would shadow it in this file.
# Python module-level singletons don't need the globalThis hot-reload guard the
# original used (that was a Node --watch dev-server artifact); connect/disconnect
# is wired to FastAPI's lifespan in main.py instead.
db = Prisma()
