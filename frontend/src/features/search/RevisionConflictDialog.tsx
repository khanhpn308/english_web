import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export function RevisionConflictDialog({
  open,
  serverRevision,
  onCancel,
  onReloadSource,
  onDiscardDraft,
}: {
  open: boolean;
  serverRevision?: number;
  onCancel: () => void;
  onReloadSource: () => void;
  onDiscardDraft: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Xung đột dữ liệu</DialogTitle>
          <DialogDescription>
            Nguồn dữ liệu đã bị thay đổi bởi một tiến trình khác (phiên bản hiện tại trên máy chủ: {serverRevision ?? 'không rõ'}). 
            Bạn có thể tải lại mã phiên bản mới nhất để tiếp tục lưu bản nháp của mình (ghi đè dữ liệu trên máy chủ), hoặc hủy bản nháp để tải lại trang.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0 flex-col sm:flex-row">
          <Button type="button" variant="outline" onClick={onDiscardDraft}>
            Hủy bản nháp và tải lại
          </Button>
          <Button type="button" onClick={onReloadSource}>
            Cập nhật mã phiên bản để lưu đè
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
