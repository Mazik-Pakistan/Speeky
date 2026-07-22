/*
  Warnings:

  - Made the column `name` on table `users` required. This step will fail if there are existing NULL values in that column.

*/
-- AlterTable
ALTER TABLE "users" ALTER COLUMN "name" SET NOT NULL;

-- CreateTable
CREATE TABLE "kv_entries" (
    "namespace" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "userId" TEXT,
    "value" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "kv_entries_pkey" PRIMARY KEY ("namespace","key")
);

-- CreateTable
CREATE TABLE "signup_otps" (
    "email" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "password" TEXT NOT NULL,
    "codeHash" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "signup_otps_pkey" PRIMARY KEY ("email")
);

-- CreateIndex
CREATE INDEX "kv_entries_namespace_idx" ON "kv_entries"("namespace");

-- CreateIndex
CREATE INDEX "kv_entries_userId_idx" ON "kv_entries"("userId");

-- CreateIndex
CREATE INDEX "baseline_assessments_userId_completedAt_idx" ON "baseline_assessments"("userId", "completedAt");

-- CreateIndex
CREATE INDEX "password_reset_tokens_userId_usedAt_idx" ON "password_reset_tokens"("userId", "usedAt");

-- CreateIndex
CREATE INDEX "prompt_logs_userId_kind_createdAt_idx" ON "prompt_logs"("userId", "kind", "createdAt");

-- CreateIndex
CREATE INDEX "reassessment_requests_userId_cycleCount_idx" ON "reassessment_requests"("userId", "cycleCount");

-- CreateIndex
CREATE INDEX "refresh_tokens_userId_idx" ON "refresh_tokens"("userId");
