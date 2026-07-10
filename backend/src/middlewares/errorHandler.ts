import type { ErrorRequestHandler } from "express";

interface AppError extends Error {
  statusCode?: number;
  status?: "fail" | "error";
  isOperational?: boolean;
}

export const errorHandler: ErrorRequestHandler = (err: AppError, req, res, _next) => {
  console.error({
    message: err.message,
    stack: err.stack,
  });

  const statusCode = err.statusCode ?? 500;
  res.status(statusCode).json({
    status: err.status ?? "error",
    message: err.isOperational ? err.message : "Something went wrong!",
  });
};
