#!/bin/sh
set -eu

compose="docker compose -p community-w0 --env-file docker/community.env.example -f docker/community.compose.yml"
run_dir=$(mktemp -d)
cleanup() {
  if [ -f "$run_dir/owned.json" ]; then
    $compose run --rm --no-deps -v "$run_dir:/ui-run:ro" backend python manage.py shell -c "import json; from django.contrib.auth import get_user_model; from community.models import CommunityPost; names=json.load(open('/ui-run/owned.json'))['users']; User=get_user_model(); users=User.objects.filter(username__in=names); CommunityPost.objects.filter(owner__in=users).delete(); users.delete()" >/dev/null
  fi
  find "$run_dir" -depth -delete
}
trap cleanup EXIT
$compose up -d --wait
docker run --rm --network host -v "$PWD/docker:/tests:ro" -v "$run_dir:/results" mcr.microsoft.com/playwright:v1.63.0-noble sh -lc \
  'npm install --prefix /tmp/pw --no-audit --no-fund --loglevel=error playwright@1.63.0 >/dev/null && node /tests/community_ui_e2e.mjs'
