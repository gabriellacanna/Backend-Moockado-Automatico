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
Create the name of the service account to use
*/}}
{{- define "backend-mockado.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create }}
{{- default (include "backend-mockado.fullname" .) .Values.security.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.security.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the collector service account to use
*/}}
{{- define "backend-mockado.collector.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create }}
{{- printf "%s-collector" (include "backend-mockado.fullname" .) }}
{{- else }}
{{- default "default" .Values.security.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the wiremock-loader service account to use
*/}}
{{- define "backend-mockado.wiremock-loader.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create }}
{{- printf "%s-wiremock-loader" (include "backend-mockado.fullname" .) }}
{{- else }}
{{- default "default" .Values.security.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the wiremock service account to use
*/}}
{{- define "backend-mockado.wiremock.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create }}
{{- printf "%s-wiremock" (include "backend-mockado.fullname" .) }}
{{- else }}
{{- default "default" .Values.security.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get the Redis URL
*/}}
{{- define "backend-mockado.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- if .Values.redis.auth.enabled }}
redis://:{{ .Values.redis.auth.password }}@{{ include "backend-mockado.fullname" . }}-redis-master:6379
{{- else }}
redis://{{ include "backend-mockado.fullname" . }}-redis-master:6379
{{- end }}
{{- else }}
redis://localhost:6379
{{- end }}
{{- end }}

{{/*
Get the WireMock URL
*/}}
{{- define "backend-mockado.wiremockUrl" -}}
{{- if .Values.wiremock.enabled }}
http://{{ include "backend-mockado.fullname" . }}-wiremock:{{ .Values.wiremock.service.port }}
{{- else }}
http://localhost:8080
{{- end }}
{{- end }}

{{/*
Create image pull secrets
*/}}
{{- define "backend-mockado.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Get storage class name
*/}}
{{- define "backend-mockado.storageClassName" -}}
{{- if .Values.global.storageClass }}
{{- .Values.global.storageClass }}
{{- else }}
{{- "" }}
{{- end }}
{{- end }}

{{/*
Common security context
*/}}
{{- define "backend-mockado.securityContext" -}}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Common container security context
*/}}
{{- define "backend-mockado.containerSecurityContext" -}}
capabilities:
  drop:
    - ALL
readOnlyRootFilesystem: true
allowPrivilegeEscalation: false
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Common resource limits
*/}}
{{- define "backend-mockado.resources" -}}
{{- if . }}
resources:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Common node selector
*/}}
{{- define "backend-mockado.nodeSelector" -}}
{{- if . }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Common tolerations
*/}}
{{- define "backend-mockado.tolerations" -}}
{{- if . }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Common affinity
*/}}
{{- define "backend-mockado.affinity" -}}
{{- if . }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Validate configuration
*/}}
{{- define "backend-mockado.validateConfig" -}}
{{- if and .Values.collector.enabled (not .Values.redis.enabled) }}
{{- fail "Redis must be enabled when collector is enabled" }}
{{- end }}
{{- if and .Values.wireMockLoader.enabled (not .Values.wiremock.enabled) }}
{{- fail "WireMock must be enabled when WireMock Loader is enabled" }}
{{- end }}
{{- if and .Values.wireMockLoader.enabled (not .Values.redis.enabled) }}
{{- fail "Redis must be enabled when WireMock Loader is enabled" }}
{{- end }}
{{- end }}