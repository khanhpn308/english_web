import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ApiError, apiClient } from '@/shared/api/client';
import { RevisionConflictDialog } from './RevisionConflictDialog';
import type { components } from '@/shared/api/generated';
import { verificationLabels } from './SearchPage';

type WordFormDetail = components['schemas']['WordFormDetail'];
type SourceFile = components['schemas']['SourceFile'];
type PatchWordFormRequest = components['schemas']['PatchWordFormRequest'];
type EditMeaning = components['schemas']['EditMeaning'];
type EditExample = components['schemas']['EditExample'];
type SourcePage = components['schemas']['Page_SourceFile_'];

interface EditWordFormProps {
  wordForm: WordFormDetail;
  sourceId: string;
  noteDate: string;
  onCancel: () => void;
  onSuccess: (newRevision: number) => void;
}

export function EditWordForm({ wordForm, sourceId, noteDate, onCancel, onSuccess }: EditWordFormProps) {
  const [source, setSource] = useState<SourceFile | null>(null);
  const [loadingSource, setLoadingSource] = useState(true);
  const [sourceError, setSourceError] = useState<string | null>(null);

  const [meaningsEn, setMeaningsEn] = useState<EditMeaning[]>(wordForm.meaningsEn);
  const [meaningsVi, setMeaningsVi] = useState<EditMeaning[]>(wordForm.meaningsVi);
  const [examples, setExamples] = useState<EditExample[]>(wordForm.examples);
  const [ipaUs, setIpaUs] = useState(wordForm.ipaUs ?? '');
  const [cambridgeUrl, setCambridgeUrl] = useState(wordForm.cambridgeUrl ?? '');

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<{ message: string; fields?: { field: string; reason: string }[] } | null>(null);

  const [conflictRevision, setConflictRevision] = useState<number | undefined>();
  const [showConflict, setShowConflict] = useState(false);
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  useEffect(() => {
    let active = true;
    const fetchSource = async () => {
      try {
        const page = await apiClient<SourcePage>(`/api/v1/sources?noteDate=${encodeURIComponent(noteDate)}`);
        if (!active) return;
        const validSource = page.data.find(s => s.id === sourceId && s.status === 'VALID');
        if (!validSource) {
          setSourceError('Nguồn không hợp lệ, không tồn tại hoặc trạng thái hiện tại không cho phép chỉnh sửa.');
        } else {
          setSource(validSource);
        }
      } catch (err) {
        if (active) setSourceError('Không thể tải thông tin nguồn. Vui lòng kiểm tra kết nối.');
      } finally {
        if (active) setLoadingSource(false);
      }
    };
    fetchSource();
    return () => { active = false; };
  }, [noteDate, sourceId]);

  const reloadSource = async () => {
    setLoadingSource(true);
    try {
      const page = await apiClient<SourcePage>(`/api/v1/sources?noteDate=${encodeURIComponent(noteDate)}`);
      const validSource = page.data.find(s => s.id === sourceId && s.status === 'VALID');
      if (!validSource) {
        setSourceError('Nguồn không hợp lệ hoặc đã bị xóa.');
      } else {
        setSource(validSource);
        setShowConflict(false);
        setSaveError(null);
      }
    } catch {
      setSourceError('Lỗi khi cập nhật nguồn.');
    } finally {
      setLoadingSource(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!source || saving) return;
    setSaving(true);
    setSaveError(null);

    const payload: PatchWordFormRequest = {
      sourceId,
      sourceRevision: source.revision,
      meaningsEn,
      meaningsVi,
      examples,
      ipaUs: ipaUs.trim() || null,
      cambridgeUrl: cambridgeUrl.trim() || null,
    };

    try {
      const result = await apiClient<components['schemas']['WordFormMutationResult']>(`/api/v1/word-forms/${encodeURIComponent(wordForm.id)}`, {
        method: 'PATCH',
        headers: {
          'Idempotency-Key': idempotencyKey,
          'If-Match': source.etag,
        },
        body: JSON.stringify(payload),
      });
      onSuccess(result.sourceRevision);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'REVISION_CONFLICT' && err.details?.kind === 'CONFLICT') {
          setConflictRevision(err.details.currentRevision);
          setShowConflict(true);
        } else if (err.details?.kind === 'FIELD_ERRORS') {
          setSaveError({ message: 'Dữ liệu không hợp lệ.', fields: err.details.fields });
        } else {
          setSaveError({ message: err.message || 'Lỗi khi lưu dữ liệu.' });
        }
      } else {
        setSaveError({ message: 'Lỗi mạng hoặc máy chủ. Bản nháp của bạn vẫn được giữ.' });
      }
    } finally {
      setSaving(false);
    }
  };

  if (loadingSource) return <p role="status">Đang tải thông tin nguồn...</p>;
  if (sourceError) return <div role="alert" className="space-y-3"><p>{sourceError}</p><Button onClick={onCancel}>Quay lại</Button></div>;

  const controlClass = "w-full rounded-md border border-input bg-background px-3 py-2 text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring";

  return (
    <Card>
      <CardContent className="pt-6">
        <form onSubmit={handleSave} className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Chỉnh sửa: {wordForm.lemma}</h2>
            <div className="text-sm text-muted-foreground">Mã nguồn: {source?.revision}</div>
          </div>

          {/* Tiếng Anh */}
          <div className="space-y-3">
            <h3 className="text-xl font-medium">Nghĩa tiếng Anh</h3>
            {meaningsEn.map((m, i) => (
              <div key={i} className="flex gap-2 items-start">
                <input required value={m.text} onChange={e => setMeaningsEn(prev => { const n = [...prev]; n[i].text = e.target.value; return n; })} className={controlClass} />
                <Button type="button" variant="outline" onClick={() => setMeaningsEn(prev => prev.filter((_, idx) => idx !== i))}>Xóa</Button>
              </div>
            ))}
            <Button type="button" variant="outline" onClick={() => setMeaningsEn(prev => [...prev, { text: '', verificationStatus: 'UNVERIFIED' }])}>Thêm nghĩa tiếng Anh</Button>
          </div>

          {/* Tiếng Việt */}
          <div className="space-y-3">
            <h3 className="text-xl font-medium">Nghĩa tiếng Việt</h3>
            {meaningsVi.map((m, i) => (
              <div key={i} className="flex gap-2 items-start">
                <input required value={m.text} onChange={e => setMeaningsVi(prev => { const n = [...prev]; n[i].text = e.target.value; return n; })} className={controlClass} />
                <Button type="button" variant="outline" onClick={() => setMeaningsVi(prev => prev.filter((_, idx) => idx !== i))}>Xóa</Button>
              </div>
            ))}
            <Button type="button" variant="outline" onClick={() => setMeaningsVi(prev => [...prev, { text: '', verificationStatus: 'UNVERIFIED' }])}>Thêm nghĩa tiếng Việt</Button>
          </div>

          {/* Ví dụ */}
          <div className="space-y-3">
            <h3 className="text-xl font-medium">Ví dụ</h3>
            {examples.map((ex, i) => (
              <div key={i} className="space-y-2 border p-3 rounded-md">
                <div>
                  <label className="block text-sm font-medium">Tiếng Anh</label>
                  <input required value={ex.english} onChange={e => setExamples(prev => { const n = [...prev]; n[i].english = e.target.value; return n; })} className={controlClass} />
                </div>
                <div>
                  <label className="block text-sm font-medium">Tiếng Việt</label>
                  <input required value={ex.vietnamese} onChange={e => setExamples(prev => { const n = [...prev]; n[i].vietnamese = e.target.value; return n; })} className={controlClass} />
                </div>
                <Button type="button" variant="outline" size="sm" onClick={() => setExamples(prev => prev.filter((_, idx) => idx !== i))}>Xóa ví dụ</Button>
              </div>
            ))}
            <Button type="button" variant="outline" onClick={() => setExamples(prev => [...prev, { english: '', vietnamese: '', verificationStatus: 'UNVERIFIED' }])}>Thêm ví dụ</Button>
          </div>

          <div className="space-y-1">
            <label className="block font-medium">IPA Mỹ</label>
            <input value={ipaUs} onChange={e => setIpaUs(e.target.value)} className={controlClass} />
          </div>

          <div className="space-y-1">
            <label className="block font-medium">Liên kết Cambridge</label>
            <input type="url" value={cambridgeUrl} onChange={e => setCambridgeUrl(e.target.value)} className={controlClass} />
          </div>

          {saveError && (
            <div role="alert" className="text-destructive font-medium">
              <p>{saveError.message}</p>
              {saveError.fields && (
                <ul className="list-disc pl-5 mt-1">
                  {saveError.fields.map((f, i) => <li key={i}>{f.field}: {f.reason}</li>)}
                </ul>
              )}
            </div>
          )}

          <div className="flex gap-3">
            <Button type="submit" disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu thay đổi'}</Button>
            <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>Hủy</Button>
          </div>
        </form>

        <RevisionConflictDialog
          open={showConflict}
          serverRevision={conflictRevision}
          onCancel={() => setShowConflict(false)}
          onDiscardDraft={onCancel}
          onReloadSource={reloadSource}
        />
      </CardContent>
    </Card>
  );
}
