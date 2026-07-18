-- CreateEnum
CREATE TYPE "AssessmentStatus" AS ENUM ('UNASSESSED', 'IN_PROGRESS', 'COMPLETED', 'PLATEAUED');

-- CreateEnum
CREATE TYPE "LearningLevel" AS ENUM ('BEGINNER', 'ELEMENTARY', 'INTERMEDIATE', 'UPPER_INTERMEDIATE', 'ADVANCED', 'PROFICIENT');

-- CreateEnum
CREATE TYPE "PromptKind" AS ENUM ('SKIP_ASSESSMENT', 'REASSESSMENT');

-- AlterTable
ALTER TABLE "users" ADD COLUMN     "assessmentStatus" "AssessmentStatus" NOT NULL DEFAULT 'UNASSESSED',
ADD COLUMN     "learningLevel" "LearningLevel",
ALTER COLUMN "avatarUrl" SET DEFAULT 'user.webp';

-- CreateTable
CREATE TABLE "baseline_assessments" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "questionIds" TEXT[],
    "currentIndex" INTEGER NOT NULL DEFAULT 0,
    "responses" JSONB NOT NULL DEFAULT '[]',
    "fluencyScore" DOUBLE PRECISION,
    "vocabularyScore" DOUBLE PRECISION,
    "pronunciationScore" DOUBLE PRECISION,
    "confidenceScore" DOUBLE PRECISION,
    "learningLevel" "LearningLevel",
    "isFlagged" BOOLEAN NOT NULL DEFAULT false,
    "flagReason" TEXT,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "baseline_assessments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "reassessment_requests" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "requestedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "scheduledDate" TIMESTAMP(3),
    "completed" BOOLEAN NOT NULL DEFAULT false,
    "isEarlyRetake" BOOLEAN NOT NULL DEFAULT false,
    "cycleCount" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "reassessment_requests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "prompt_logs" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "kind" "PromptKind" NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "prompt_logs_pkey" PRIMARY KEY ("id")
);

-- AddForeignKey
ALTER TABLE "baseline_assessments" ADD CONSTRAINT "baseline_assessments_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "reassessment_requests" ADD CONSTRAINT "reassessment_requests_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "prompt_logs" ADD CONSTRAINT "prompt_logs_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
