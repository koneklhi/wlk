/**
 * micErrorMessage 매핑 검증.
 *
 * 브라우저 E2E 로는 덮을 수 없다 — headless Chromium 은 실제 오디오 장치가 없어서
 * 권한을 허용하든 거부하든 항상 NotSupportedError 를 낸다(실측). 사용자가 실제로 겪는
 * NotAllowedError/NotFoundError 분기는 여기서만 검증된다.
 */
import { describe, expect, it } from 'vitest';
import { micErrorMessage } from './useAudioRecorder';

const domEx = (name: string) => new DOMException('Permission denied', name);

describe('micErrorMessage', () => {
  it('권한 거부는 자물쇠 아이콘 안내로 이어진다', () => {
    expect(micErrorMessage(domEx('NotAllowedError'))).toContain('마이크 권한이 거부되었습니다');
    expect(micErrorMessage(domEx('NotAllowedError'))).toContain('자물쇠');
  });

  it('SecurityError 도 권한 문제로 묶는다', () => {
    expect(micErrorMessage(domEx('SecurityError'))).toContain('마이크 권한이 거부되었습니다');
  });

  it('장치 없음은 Windows 소리 설정을 가리킨다', () => {
    for (const n of ['NotFoundError', 'OverconstrainedError']) {
      expect(micErrorMessage(domEx(n))).toContain('마이크 장치를 찾을 수 없습니다');
    }
  });

  it('장치 점유는 다른 프로그램을 가리킨다', () => {
    expect(micErrorMessage(domEx('NotReadableError'))).toContain('다른 프로그램');
  });

  it('모르는 오류도 원문을 잃지 않는다', () => {
    // NotSupportedError 처럼 분류되지 않은 것도 화면에서 원인을 볼 수 있어야 한다.
    expect(micErrorMessage(domEx('NotSupportedError'))).toContain('Permission denied');
    expect(micErrorMessage(new Error('boom'))).toContain('boom');
    expect(micErrorMessage('그냥 문자열')).toContain('그냥 문자열');
  });
});
