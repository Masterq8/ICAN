const stopReasons: Record<string, string> = {
  tool_submission_rejected: '模型未能提交符合约束的工具结果',
  model_request_failed: '模型请求未完成',
  model_unavailable: '生成服务不可用',
  model_output_truncated: '模型输出达到长度上限，结果未保存',
  model_timeout: '模型请求超时',
  budget_exhausted: '本次任务预算已用尽',
  record_save_failed: '模型已返回结果，但研究记录保存失败；请先检查历史记录',
}

const failureCodes: Record<string, string> = {
  'generation:ModelUnavailable': '生成服务不可用',
  'generation:ModelOutputTruncated': '模型输出达到长度上限，未形成完整信息卡',
  'generation:ModelTimeout': '模型请求超时',
}

export function cardStopReasonLabel(reason: string): string {
  return stopReasons[reason] ?? reason
}

export function cardFailureLabel(code: string | null | undefined): string {
  if (!code) return '未形成可提交的信息卡'
  return failureCodes[code] ?? code
}
