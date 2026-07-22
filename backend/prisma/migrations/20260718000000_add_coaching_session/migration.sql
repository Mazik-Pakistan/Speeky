-- CreateEnum
CREATE TYPE "CoachingScenario" AS ENUM ('EMAIL_WRITING', 'CLIENT_COMMUNICATION', 'MEETING_COMMUNICATION', 'PRESENTATION_PREP', 'GENERAL_WORKPLACE');

-- CreateEnum
CREATE TYPE "CoachingInputMode" AS ENUM ('TEXT', 'AUDIO');

-- CreateEnum
CREATE TYPE "CoachingStatus" AS ENUM ('IN_PROGRESS', 'COMPLETED', 'ENDED_EARLY');

-- CreateTable
CREATE TABLE "coaching_sessions" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "scenario" "CoachingScenario" NOT NULL,
    "inputMode" "CoachingInputMode" NOT NULL,
    "status" "CoachingStatus" NOT NULL DEFAULT 'IN_PROGRESS',
    "promptText" TEXT NOT NULL,
    "submission" TEXT,
    "turns" JSONB NOT NULL DEFAULT '[]',
    "audioFeatures" JSONB,
    "professionalTone" DOUBLE PRECISION,
    "clarityScore" DOUBLE PRECISION,
    "effectivenessScore" DOUBLE PRECISION,
    "fluencyScore" DOUBLE PRECISION,
    "vocabularyScore" DOUBLE PRECISION,
    "pronunciationScore" DOUBLE PRECISION,
    "confidenceScore" DOUBLE PRECISION,
    "feedback" JSONB,
    "flags" JSONB NOT NULL DEFAULT '[]',
    "metObjective" BOOLEAN,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "coaching_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "coaching_sessions_userId_idx" ON "coaching_sessions"("userId");

-- AddForeignKey
ALTER TABLE "coaching_sessions" ADD CONSTRAINT "coaching_sessions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
