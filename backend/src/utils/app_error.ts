import { RequestHandler } from "express";

export const catchAsync = (fn: RequestHandler): RequestHandler => {
  return (req, res, next) => fn(req, res, next).catch(next);
};

class AppError extends Error {
  statusCode: number;
  status: "fail" | "error";
  isOperational = true;

  constructor(message: string, statusCode = 500) {
    super(message);

    this.statusCode = statusCode;
    this.status = `${statusCode}`.startsWith("4") ? "fail" : "error";
    Error.captureStackTrace(this, this.constructor);
  }
}

export default AppError;
