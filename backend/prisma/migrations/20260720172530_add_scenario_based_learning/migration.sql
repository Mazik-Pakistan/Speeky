-- CreateTable
CREATE TABLE "scenario_sessions" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "scenarioKey" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'in_progress',
    "turns" JSONB NOT NULL DEFAULT '[]',
    "targetVocab" TEXT[],
    "vocabUsed" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "politenessScore" DOUBLE PRECISION,
    "vocabularyScore" DOUBLE PRECISION,
    "confidenceScore" DOUBLE PRECISION,
    "metGoal" BOOLEAN,
    "flags" JSONB NOT NULL DEFAULT '[]',
    "summary" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "scenario_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "custom_scenarios" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "persona" TEXT NOT NULL,
    "systemPrompt" TEXT NOT NULL,
    "openingLine" TEXT,
    "targetVocab" TEXT[],
    "goalType" TEXT NOT NULL DEFAULT 'roleplay',
    "corporateTone" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "custom_scenarios_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "scenario_sessions_userId_idx" ON "scenario_sessions"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "custom_scenarios_title_key" ON "custom_scenarios"("title");

-- AddForeignKey
ALTER TABLE "scenario_sessions" ADD CONSTRAINT "scenario_sessions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
