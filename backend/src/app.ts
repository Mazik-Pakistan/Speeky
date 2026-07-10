import cors from "cors";
import express, { NextFunction, Request, Response } from "express";
import { env } from "./config/env";
import AppError from "./utils/app_error";
import { errorHandler } from "./middlewares/errorHandler";
import authRoutes from "./routes/auth_routes";

const app = express();

app.use(express.json());
app.use(cors({ origin: env.CLIENT_ORIGINS, credentials: true }));

app.get("/health", (_req: Request, res: Response) => {
  res.setHeader("Content-Type", "text/html");
  res.status(200).send("<h1>Speeky API is running!</h1>");
});
app.use("/api/auth", authRoutes);

app.all("/{*path}", (req: Request, res: Response, next: NextFunction) => {
  next(new AppError(`Route not found: ${req.url}`, 404));
});
app.use(errorHandler);

export default app;
