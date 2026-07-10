import { RequestHandler } from "express";

function isValidCredentials(email: string, password: string): email is string {
  return /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email) && password.length >= 8;
}
