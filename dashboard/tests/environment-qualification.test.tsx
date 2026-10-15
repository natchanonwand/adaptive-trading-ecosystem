import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { CampaignAuthorization } from '../src/workbench/CampaignAuthorization';

it('separates qualified environment from campaign authorization', () => {
  const authorize = vi.fn();
  render(
    <CampaignAuthorization
      busy={false}
      authorize={authorize}
      review={{
        state: 'NOT_AUTHORIZED',
        start_eligible: false,
        authorization_eligible: false,
        environment_qualification: {
          state: 'READY',
          account_context: 'RUNTIME_ACCOUNT_CONTEXT_ACCEPTED',
          identity: 'a'.repeat(64),
        },
      }}
    />,
  );
  expect(screen.getByText('EXECUTION ENVIRONMENT: READY')).toBeTruthy();
  expect(screen.getByText('ACCOUNT CONTEXT: RUNTIME_ACCOUNT_CONTEXT_ACCEPTED')).toBeTruthy();
  expect(
    (screen.getByRole('button', { name: 'Authorize campaign' }) as HTMLButtonElement).disabled,
  ).toBe(true);
  expect(authorize).not.toHaveBeenCalled();
});
