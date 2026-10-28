import Modal from "./Modal";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message: string;
  loading?: boolean;
  /** Button text; defaults to Delete / Deleting… */
  confirmLabel?: string;
  loadingLabel?: string;
}

export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = "Confirm",
  message,
  loading,
  confirmLabel = "Delete",
  loadingLabel = "Deleting…",
}: Props) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm">
      <p className="text-sm text-gray-600 mb-6">{message}</p>
      <div className="flex gap-3 justify-end">
        <button className="btn-secondary" onClick={onClose}>
          Cancel
        </button>
        <button className="btn-danger" onClick={onConfirm} disabled={loading}>
          {loading ? loadingLabel : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
