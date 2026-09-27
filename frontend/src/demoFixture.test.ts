import { describe, expect, it } from 'vitest'
import fixture from './demo/swin-case.json'
import { hydrateAndValidateDemoFixture, requiredDemoFields } from './demoFixture'

describe('readonly Swin demo fixture', () => {
  it('covers every visible card field with clickable source evidence', () => {
    const demo = hydrateAndValidateDemoFixture(fixture)
    const latest = demo.history.extraction[0]

    expect(new Set(latest.fields.map(field => field.name))).toEqual(
      new Set(requiredDemoFields),
    )
    expect(latest.fields.every(field => field.claims.length > 0)).toBe(true)
    expect(
      latest.fields
        .flatMap(field => field.claims)
        .every(claim => claim.evidence.length > 0),
    ).toBe(true)
  })

  it('keeps paper 81.3 and repository 81.2 as separate sourced results', () => {
    const demo = hydrateAndValidateDemoFixture(fixture)
    const results = demo.history.extraction[0].fields.filter(
      field => field.name === 'result',
    )

    expect(results.map(field => field.value)).toEqual(
      expect.arrayContaining([
        '论文 Table 1(a)：Swin-T 在 ImageNet-1K、224×224 下 top-1 为 81.3%',
        '官方仓库模型表：对应 Swin-T checkpoint 的 top-1 为 81.2%',
      ]),
    )
    expect(
      new Set(
        results.flatMap(field =>
          field.claims.flatMap(claim =>
            claim.evidence.map(item => item.source.source_type),
          ),
        ),
      ),
    ).toEqual(new Set(['paper', 'documentation']))
  })

  it('preserves stable revision chains', () => {
    const demo = hydrateAndValidateDemoFixture(fixture)

    expect(demo.history.screening[0].revision_of).toBe(
      demo.history.screening[1].record_id,
    )
    expect(demo.history.extraction[0].revision_of).toBe(
      demo.history.extraction[1].record_id,
    )
  })

  it('rejects a claim quote that is absent from its bound evidence', () => {
    const brokenFixture = structuredClone(fixture)
    brokenFixture.history.extraction[0].fields[0].claims[0].claim.quote =
      '这段引文不存在于任何证据中'

    expect(() => hydrateAndValidateDemoFixture(brokenFixture)).toThrow(
      'Readonly demo quote is not present in evidence',
    )
  })
})
