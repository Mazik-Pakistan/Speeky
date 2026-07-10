import app from "./app";
import { env } from "./config/env";

process.on("uncaughtException", (err) => {
    console.error("Uncaught Exception:", err);
    process.exit(1);
});

const server = app.listen(env.PORT, () =>
    console.log(`Speaky-AI backend listening on ${env.PORT}`),
);

process.on("unhandledRejection", (reason, promise) => {
    console.error("Unhandled Rejection at:", promise, "reason:", reason);
    server.close(() => process.exit(1));
});
