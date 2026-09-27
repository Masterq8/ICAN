import { describe, expect, it } from 'vitest'
import { cardFailureLabel, cardStopReasonLabel } from './cardStatus'

describe('research card failure labels', () => {
  it('explains a length-limited response without calling the service unavailable', () => {
    expect(cardFailureLabel('generation:ModelOutputTruncated')).toBe(
      '模型输出达到长度上限，未形成完整信息卡',
    )
    expect(cardStopReasonLabel('model_output_truncated')).toBe(
      '模型输出达到长度上限，结果未保存',
    )
  })
})
