'use client';

import { TranscriptTurn } from '@/types';

interface AudioTranscriptProps {
  turns: TranscriptTurn[];
}

// What RIA and the customer said, turn by turn
export default function AudioTranscript({ turns }: AudioTranscriptProps) {
  return (
    <div className="card">
      <div className="card-h">
        <h3>Call Transcript</h3>
        <span className="sub">{turns.length} turns</span>
      </div>
      <div className="card-b">
        <div className="transcript">
          {turns.map((t, idx) => (
            <div key={idx} className={`turn ${t.who.toUpperCase() === 'RIA' ? 'ria' : ''}`}>
              <div>
                <div className="who">{t.who}</div>
                <div className="lang">{t.lang.toUpperCase()}</div>
              </div>
              <div className="txt">
                {t.txt}
                {t.cut && (
                  <span className="chip c-grey turn-cut" title="The customer started talking and RIA stopped here">
                    cut off
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
