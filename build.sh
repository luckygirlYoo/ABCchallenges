#!/bin/bash
# Vercel 빌드 스크립트: web/ + data/ → dist/
set -e

mkdir -p dist/data

# web 폴더 내용을 dist 루트에 복사
cp -r web/* dist/

# data 폴더의 CSV/JSON을 dist/data에 복사
cp data/*.csv dist/data/ 2>/dev/null || true
cp data/*.json dist/data/ 2>/dev/null || true

# JS 파일의 상대 경로를 수정: ../data/ → ./data/
sed -i "s|'../data/|'./data/|g" dist/app.js
sed -i "s|\"../data/|\"./data/|g" dist/app.js
sed -i "s|'../data/|'./data/|g" dist/admin.js
sed -i "s|\"../data/|\"./data/|g" dist/admin.js

echo "✅ Vercel 빌드 완료! dist/ 구조:"
ls -la dist/
echo "--- dist/data/ ---"
ls -la dist/data/
