'use client';

import { useApp } from '@/context/AppContext';

export default function Modal() {
  const { modal, closeModal } = useApp();
  if (!modal.isOpen) return null;

  return (
    <div className="modal-bg" onClick={closeModal}>
      <div className={`modal ${modal.wide ? 'wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="m-h">
          <h3>{modal.title}</h3>
        </div>
        <div className="m-b">{modal.body}</div>
        {modal.footer && <div className="m-f">{modal.footer}</div>}
      </div>
    </div>
  );
}
