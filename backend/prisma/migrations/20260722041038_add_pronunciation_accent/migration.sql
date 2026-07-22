-- CreateEnum
CREATE TYPE "AccentAssessmentStatus" AS ENUM ('COMPLETED', 'REJECTED_NO_SPEECH', 'REJECTED_TOO_QUIET', 'REJECTED_TOO_NOISY', 'REJECTED_INCOMPLETE', 'REJECTED_MULTIPLE_VOICES');

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
CREATE TABLE "accent_assessments" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "passageId" TEXT NOT NULL,
    "status" "AccentAssessmentStatus" NOT NULL,
    "rejectionReason" TEXT,
    "transcript" TEXT,
    "pronunciationScore" DOUBLE PRECISION,
    "stressScore" DOUBLE PRECISION,
    "rhythmScore" DOUBLE PRECISION,
    "intonationScore" DOUBLE PRECISION,
    "clarityScore" DOUBLE PRECISION,
    "weakPoints" JSONB NOT NULL DEFAULT '[]',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "accent_assessments_pkey" PRIMARY KEY ("id")
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
CREATE INDEX "accent_assessments_userId_completedAt_idx" ON "accent_assessments"("userId", "completedAt");

-- CreateIndex
CREATE INDEX "accent_profiles_userId_createdAt_idx" ON "accent_profiles"("userId", "createdAt");

-- AddForeignKey
ALTER TABLE "pronunciation_attempts" ADD CONSTRAINT "pronunciation_attempts_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "accent_assessments" ADD CONSTRAINT "accent_assessments_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "accent_profiles" ADD CONSTRAINT "accent_profiles_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "accent_profiles" ADD CONSTRAINT "accent_profiles_sourceAssessmentId_fkey" FOREIGN KEY ("sourceAssessmentId") REFERENCES "accent_assessments"("id") ON DELETE CASCADE ON UPDATE CASCADE;
