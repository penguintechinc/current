{{/*
Expand the name of the chart.
*/}}
{{- define "current.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "current.fullname" -}}
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
{{- define "current.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "current.labels" -}}
helm.sh/chart: {{ include "current.chart" . }}
{{ include "current.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "current.selectorLabels" -}}
app.kubernetes.io/name: {{ include "current.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Flask Backend selector labels
*/}}
{{- define "current.flaskBackend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "current.name" . }}-flask-backend
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: flask-backend
{{- end }}

{{/*
WebUI selector labels
*/}}
{{- define "current.webui.selectorLabels" -}}
app.kubernetes.io/name: {{ include "current.name" . }}-webui
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: webui
{{- end }}
