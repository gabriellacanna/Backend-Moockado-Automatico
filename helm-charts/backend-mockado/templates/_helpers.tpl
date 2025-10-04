{{/*
Expand the name of the chart.
*/}}
{{- define "backend-mockado.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "backend-mockado.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "backend-mockado.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "backend-mockado.labels" -}}
helm.sh/chart: {{ include "backend-mockado.chart" . }}
{{ include "backend-mockado.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "backend-mockado.selectorLabels" -}}
app.kubernetes.io/name: {{ include "backend-mockado.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "backend-mockado.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "backend-mockado.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the collector service account to use
*/}}
{{- define "backend-mockado.collector.serviceAccountName" -}}
{{- if .Values.collector.serviceAccount.create }}
{{- default (printf "%s-collector" (include "backend-mockado.fullname" .)) .Values.collector.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.collector.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the wiremock-loader service account to use
*/}}
{{- define "backend-mockado.wiremock-loader.serviceAccountName" -}}
{{- if .Values.wireMockLoader.serviceAccount.create }}
{{- default (printf "%s-wiremock-loader" (include "backend-mockado.fullname" .)) .Values.wireMockLoader.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.wireMockLoader.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the wiremock service account to use
*/}}
{{- define "backend-mockado.wiremock.serviceAccountName" -}}
{{- if .Values.wiremock.serviceAccount.create }}
{{- default (printf "%s-wiremock" (include "backend-mockado.fullname" .)) .Values.wiremock.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.wiremock.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Collector labels
*/}}
{{- define "backend-mockado.collector.labels" -}}
{{ include "backend-mockado.labels" . }}
app.kubernetes.io/component: collector
{{- end }}

{{/*
Collector selector labels
*/}}
{{- define "backend-mockado.collector.selectorLabels" -}}
{{ include "backend-mockado.selectorLabels" . }}
app.kubernetes.io/component: collector
{{- end }}

{{/*
WireMock Loader labels
*/}}
{{- define "backend-mockado.wiremock-loader.labels" -}}
{{ include "backend-mockado.labels" . }}
app.kubernetes.io/component: wiremock-loader
{{- end }}

{{/*
WireMock Loader selector labels
*/}}
{{- define "backend-mockado.wiremock-loader.selectorLabels" -}}
{{ include "backend-mockado.selectorLabels" . }}
app.kubernetes.io/component: wiremock-loader
{{- end }}

{{/*
WireMock labels
*/}}
{{- define "backend-mockado.wiremock.labels" -}}
{{ include "backend-mockado.labels" . }}
app.kubernetes.io/component: wiremock
{{- end }}

{{/*
WireMock selector labels
*/}}
{{- define "backend-mockado.wiremock.selectorLabels" -}}
{{ include "backend-mockado.selectorLabels" . }}
app.kubernetes.io/component: wiremock
{{- end }}

{{/*
Redis URL
*/}}
{{- define "backend-mockado.redisUrl" -}}
{{- if .Values.redis.external.enabled }}
{{- .Values.redis.external.host }}:{{ .Values.redis.external.port }}
{{- else }}
redis://{{ include "backend-mockado.fullname" . }}-redis-master:6379
{{- end }}
{{- end }}

{{/*
WireMock URL
*/}}
{{- define "backend-mockado.wiremockUrl" -}}
{{- if .Values.wiremock.external.enabled }}
{{- .Values.wiremock.external.url }}
{{- else }}
http://{{ include "backend-mockado.fullname" . }}-wiremock:{{ .Values.wiremock.service.port }}
{{- end }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "backend-mockado.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- else if .Values.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Security context
*/}}
{{- define "backend-mockado.securityContext" -}}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
{{- end }}

{{/*
Container security context
*/}}
{{- define "backend-mockado.containerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop:
  - ALL
readOnlyRootFilesystem: true
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
{{- end }}

{{/*
Node selector
*/}}
{{- define "backend-mockado.nodeSelector" -}}
{{- if . }}
nodeSelector:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Tolerations
*/}}
{{- define "backend-mockado.tolerations" -}}
{{- if . }}
tolerations:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Affinity
*/}}
{{- define "backend-mockado.affinity" -}}
{{- if . }}
affinity:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}