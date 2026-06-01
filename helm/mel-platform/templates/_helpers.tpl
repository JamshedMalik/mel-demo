{{/*
Common labels applied to all resources.
Interview point: "Consistent labeling is a platform engineering
standard — it enables filtering, monitoring, and cost tracking."
*/}}

{{- define "mel-platform.labels" -}}
app.kubernetes.io/managed-by: helm
app.kubernetes.io/part-of: mel-platform
{{- end }}

{{- define "mel-platform.edgeServiceLabels" -}}
app: edge-service
{{ include "mel-platform.labels" . }}
{{- end }}

{{- define "mel-platform.sensorSimulatorLabels" -}}
app: sensor-simulator
{{ include "mel-platform.labels" . }}
{{- end }}