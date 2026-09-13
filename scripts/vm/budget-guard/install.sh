#!/usr/bin/env bash
# Cloud Shell에서 실행. 예산/PubSub는 콘솔에서 먼저 만든다.
# VM 생성/삭제나 결제 연결 변경은 하지 않는다.
set -euo pipefail
cd "$(dirname "$0")"
PROJECT=botpikdun
REGION=asia-northeast3
FUNCTION=botpikdun-budget-guard
BUDGET_ID=bffe184a-88d3-4f06-843b-b4725503bc45
RUN_SA=budget-guard-run@$PROJECT.iam.gserviceaccount.com
EVENT_SA=budget-guard-events@$PROJECT.iam.gserviceaccount.com
BUILD_SA=budget-guard-build@$PROJECT.iam.gserviceaccount.com

gcloud services enable cloudfunctions.googleapis.com run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com eventarc.googleapis.com pubsub.googleapis.com --project="$PROJECT" --quiet
for name in budget-guard-run budget-guard-events budget-guard-build; do
  if ! gcloud iam service-accounts describe "$name@$PROJECT.iam.gserviceaccount.com" --project="$PROJECT" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --project="$PROJECT" --quiet
  fi
done
if ! gcloud iam roles describe budgetVmStopper --project="$PROJECT" >/dev/null 2>&1; then
  gcloud iam roles create budgetVmStopper --project="$PROJECT" --title='Budget VM stopper' --permissions=compute.instances.get,compute.instances.stop --stage=GA --quiet
fi
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$RUN_SA" --role="projects/$PROJECT/roles/budgetVmStopper" --condition=None --quiet >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$EVENT_SA" --role=roles/eventarc.eventReceiver --condition=None --quiet >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$BUILD_SA" --role=roles/cloudbuild.builds.builder --condition=None --quiet >/dev/null

gcloud functions deploy "$FUNCTION" --gen2 --project="$PROJECT" --region="$REGION" \
  --runtime=python312 --source=. --entry-point=limit_use \
  --trigger-topic=botpikdun-budget --trigger-service-account="$EVENT_SA" \
  --service-account="$RUN_SA" --build-service-account="projects/$PROJECT/serviceAccounts/$BUILD_SA" \
  --set-env-vars="BUDGET_ID=$BUDGET_ID" --memory=256Mi --timeout=120s \
  --min-instances=0 --max-instances=1 --retry --no-allow-unauthenticated --quiet
gcloud run services add-iam-policy-binding "$FUNCTION" --project="$PROJECT" --region="$REGION" \
  --member="serviceAccount:$EVENT_SA" --role=roles/run.invoker --quiet >/dev/null
gcloud functions describe "$FUNCTION" --gen2 --project="$PROJECT" --region="$REGION" --format='yaml(state,eventTrigger,serviceConfig.serviceAccountEmail,serviceConfig.maxInstanceCount)'
