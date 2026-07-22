/*
  Warnings:

  - You are about to drop the column `intent` on the `custom_scenarios` table. All the data in the column will be lost.
  - You are about to drop the column `safetyMode` on the `custom_scenarios` table. All the data in the column will be lost.
  - Added the required column `passageId` to the `accent_assessments` table without a default value. This is not possible if the table is not empty.
  - Added the required column `status` to the `accent_assessments` table without a default value. This is not possible if the table is not empty.

*/
-- CreateEnum
CREATE TYPE "AccentAssessmentStatus" AS ENUM ('COMPLETED', 'REJECTED_NO_SPEECH', 'REJECTED_TOO_QUIET', 'REJECTED_TOO_NOISY', 'REJECTED_INCOMPLETE', 'REJECTED_MULTIPLE_VOICES');

-- DropIndex
DROP INDEX "accent_assessments_userId_monthIndex_idx";

-- AlterTable
ALTER TABLE "accent_assessments" ADD COLUMN     "passageId" TEXT NOT NULL,
ADD COLUMN     "rejectionReason" TEXT,
ADD COLUMN     "rhythmScore" DOUBLE PRECISION,
ADD COLUMN     "status" "AccentAssessmentStatus" NOT NULL,
ADD COLUMN     "stressScore" DOUBLE PRECISION,
ADD COLUMN     "transcript" TEXT,
ADD COLUMN     "weakPoints" JSONB NOT NULL DEFAULT '[]',
ALTER COLUMN "pronunciationScore" DROP NOT NULL,
ALTER COLUMN "intonationScore" DROP NOT NULL,
ALTER COLUMN "clarityScore" DROP NOT NULL,
ALTER COLUMN "completedAt" DROP NOT NULL,
ALTER COLUMN "completedAt" DROP DEFAULT;

-- AlterTable
ALTER TABLE "custom_scenarios" DROP COLUMN "intent",
DROP COLUMN "safetyMode";

-- CreateTable
CREATE TABLE "pronunciation_attempts" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "sentenceId" TEXT NOT NULL,
    "targetText" TEXT NOT NULL,
    "transcript" TEXT NOT NULL,
    "wordResults" JSONB NOT NULL,
    "overallScore" DOUBLE PRECISION NOT NULL,
    "accentProfileTag" TEXT,
    "attemptCount" INTEGER NOT NULL DEFAULT 1,
    "backgroundVoiceDetected" BOOLEAN NOT NULL DEFAULT false,
    "disfluencyDetected" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "pronunciation_attempts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "accent_profiles" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "sourceAssessmentId" TEXT NOT NULL,
    "pronunciationScore" DOUBLE PRECISION NOT NULL,
    "stressScore" DOUBLE PRECISION NOT NULL,
    "rhythmScore" DOUBLE PRECISION NOT NULL,
    "intonationScore" DOUBLE PRECISION NOT NULL,
    "clarityScore" DOUBLE PRECISION NOT NULL,
    "weakPoints" JSONB NOT NULL,
    "exercises" JSONB NOT NULL DEFAULT '[]',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "accent_profiles_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "pronunciation_attempts_userId_idx" ON "pronunciation_attempts"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "pronunciation_attempts_userId_sentenceId_key" ON "pronunciation_attempts"("userId", "sentenceId");

-- CreateIndex
CREATE INDEX "accent_profiles_userId_createdAt_idx" ON "accent_profiles"("userId", "createdAt");

-- CreateIndex
CREATE INDEX "accent_assessments_userId_completedAt_idx" ON "accent_assessments"("userId", "completedAt");

-- AddForeignKey
ALTER TABLE "pronunciation_attempts" ADD CONSTRAINT "pronunciation_attempts_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "accent_profiles" ADD CONSTRAINT "accent_profiles_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "accent_profiles" ADD CONSTRAINT "accent_profiles_sourceAssessmentId_fkey" FOREIGN KEY ("sourceAssessmentId") REFERENCES "accent_assessments"("id") ON DELETE CASCADE ON UPDATE CASCADE;
