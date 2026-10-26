import { useCallback, useRef, useState } from 'react';

/** 开页版本冻结；后台查询刷新不能替换用户正在编辑的依据。 */
export function useEditSnapshot(code: string | undefined) {
  const loadedCode = useRef<string>();
  const version = useRef<number>(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [conflict, setConflict] = useState(false);
  const capture = useCallback((nextVersion: number) => {
    if (loadedCode.current === code) return false;
    loadedCode.current = code;
    version.current = nextVersion;
    return true;
  }, [code]);
  return {
    version,
    reloadKey,
    conflict,
    setConflict,
    capture,
    reload: () => {
      loadedCode.current = undefined;
      setReloadKey((n) => n + 1);
      setConflict(false);
    },
  };
}
