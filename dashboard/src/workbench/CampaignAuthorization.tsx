import { useState } from 'react';
import { Button, Checkbox, RetroPanel, StatusBadge } from './retro';
import { CopyValue } from './ResearchSurfaces';

export type AuthorizationReview = {
  state: string;
  review_identity?: string;
  start_eligible: boolean;
  authorization_eligible?: boolean;
  blocker?: string | null;
};

export function CampaignAuthorization({
  review,
  authorize,
  busy,
}: {
  review: AuthorizationReview;
  authorize: (identity: string) => Promise<void>;
  busy: boolean;
}) {
  const [confirmed, setConfirmed] = useState(false);
  return (
    <RetroPanel title="Execution authorization review" status={review.state}>
      <p>REFERENCE CANDIDATE · PROJECT-OWNED · PRE-REGISTERED</p>
      <p>Parameter provenance: VERIFIED · PROJECT_SOURCE</p>
      <p>GRID · 9 candidates · DEVELOPMENT maximum 9 · VALIDATION maximum 2 · Native maximum 11.</p>
      <p>
        NET_PROFIT descending, configuration identity ascending; TRADE_COUNT ≥ 10; select at most 2.
      </p>
      <p>
        EXPLORATORY_GROSS · LOCKED_OOS SEALED. Review the frozen dossier, parameters, dates and
        ordered candidate identities before confirming.
      </p>
      <StatusBadge status={review.state} />
      {review.review_identity && (
        <CopyValue label="authorization review identity" value={review.review_identity} />
      )}
      {review.blocker && <p role="status">Execution prerequisite: {review.blocker}</p>}
      <Checkbox
        label="I reviewed this exact frozen candidate, parameter space, dates, objectives, constraints and total budget of 11; authorize DEVELOPMENT and VALIDATION only."
        checked={confirmed}
        onChange={(e) => setConfirmed(e.target.checked)}
      />
      <Button
        disabled={
          busy ||
          !confirmed ||
          !review.authorization_eligible ||
          !review.review_identity ||
          review.state === 'AUTHORIZED'
        }
        onClick={() => void authorize(review.review_identity!)}
      >
        Authorize campaign
      </Button>
      <p>Authorization and Start are separate actions. Phase 5C.2B does not start a campaign.</p>
    </RetroPanel>
  );
}
