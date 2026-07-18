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

-- CreateIndex
CREATE INDEX "kv_entries_namespace_idx" ON "kv_entries"("namespace");

-- CreateIndex
CREATE INDEX "kv_entries_userId_idx" ON "kv_entries"("userId");
