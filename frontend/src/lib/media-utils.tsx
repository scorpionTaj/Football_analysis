'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import { Shield, Trophy, User } from 'lucide-react';

interface FootballBadgeProps {
  url?: string | null;
  name: string;
  size?: number;
  className?: string;
}

const FALLBACK_TEAM_BADGES: Record<string, string> = {
  'crystal palace': 'https://r2.thesportsdb.com/images/media/team/badge/ia6i3m1656014992.png',
  'valencia': 'https://r2.thesportsdb.com/images/media/team/badge/dm8l6o1656015091.png',
  'augsburg': 'https://r2.thesportsdb.com/images/media/team/badge/xqyyvq1473456209.png',
  'coventry': 'https://r2.thesportsdb.com/images/media/team/badge/uxyqys1420650993.png',
  'coventry city': 'https://r2.thesportsdb.com/images/media/team/badge/uxyqys1420650993.png',
  'schalke 04': 'https://r2.thesportsdb.com/images/media/team/badge/hnci291626207185.png',
  'eintracht frankfurt': 'https://r2.thesportsdb.com/images/media/team/badge/rurwpy1473456382.png',
  'ein frankfurt': 'https://r2.thesportsdb.com/images/media/team/badge/rurwpy1473456382.png',
  'rayo vallecano': 'https://r2.thesportsdb.com/images/media/team/badge/nzhu941656015053.png',
  'vallecano': 'https://r2.thesportsdb.com/images/media/team/badge/nzhu941656015053.png',
  'aston villa': 'https://r2.thesportsdb.com/images/media/team/badge/uwzw561783094825.png',
  'atalanta': 'https://r2.thesportsdb.com/images/media/team/badge/qix5ku1783094825.png',
  'athletic club': 'https://r2.thesportsdb.com/images/media/team/badge/myl7c31678125139.png',
  'ath bilbao': 'https://r2.thesportsdb.com/images/media/team/badge/myl7c31678125139.png',
  'alaves': 'https://r2.thesportsdb.com/images/media/team/badge/57m3q21656014949.png',
  'sevilla': 'https://r2.thesportsdb.com/images/media/team/badge/zbg6b21656015077.png',
  'real sociedad': 'https://r2.thesportsdb.com/images/media/team/badge/u19a0d1656015067.png',
  'sociedad': 'https://r2.thesportsdb.com/images/media/team/badge/u19a0d1656015067.png',
  'villarreal': 'https://r2.thesportsdb.com/images/media/team/badge/wspxwt1420650993.png',
  'wolfsburg': 'https://r2.thesportsdb.com/images/media/team/badge/wtswyr1473456885.png',
  'mainz': 'https://r2.thesportsdb.com/images/media/team/badge/trqqxv1473456578.png',
  'hoffenheim': 'https://r2.thesportsdb.com/images/media/team/badge/rqqwqq1473456488.png',
  'bologna': 'https://r2.thesportsdb.com/images/media/team/badge/qvvptv1420650993.png',
  'fiorentina': 'https://r2.thesportsdb.com/images/media/team/badge/84qbbn1656015003.png',
  'roma': 'https://r2.thesportsdb.com/images/media/team/badge/3w3j3w1656015060.png',
  'lazio': 'https://r2.thesportsdb.com/images/media/team/badge/pwtwpu1420650993.png',
  'torino': 'https://r2.thesportsdb.com/images/media/team/badge/8tvy631656015085.png',
  'monaco': 'https://r2.thesportsdb.com/images/media/team/badge/yqspqu1420650993.png',
  'lyon': 'https://r2.thesportsdb.com/images/media/team/badge/5d4f3b1656015039.png',
  'marseille': 'https://r2.thesportsdb.com/images/media/team/badge/tpuuyr1420650993.png',
  'argentina': 'https://r2.thesportsdb.com/images/media/team/badge/7a3y0t1534960309.png',
  'france': 'https://r2.thesportsdb.com/images/media/team/badge/d9l6r11534960341.png',
  'brazil': 'https://r2.thesportsdb.com/images/media/team/badge/1n4x891534960317.png',
  'england': 'https://r2.thesportsdb.com/images/media/team/badge/4vfqk01534960334.png',
  'spain': 'https://r2.thesportsdb.com/images/media/team/badge/78x8f41534960370.png',
  'germany': 'https://r2.thesportsdb.com/images/media/team/badge/8m1z981534960347.png',
  'portugal': 'https://r2.thesportsdb.com/images/media/team/badge/i0m6v21534960363.png',
  'netherlands': 'https://r2.thesportsdb.com/images/media/team/badge/97a5a81534960359.png',
  'croatia': 'https://r2.thesportsdb.com/images/media/team/badge/4l9h181534960328.png',
  'morocco': 'https://r2.thesportsdb.com/images/media/team/badge/70w2211534960357.png',
  'japan': 'https://r2.thesportsdb.com/images/media/team/badge/0o2f7t1534960355.png',
  'usa': 'https://r2.thesportsdb.com/images/media/team/badge/6t29a81534960378.png',
  'united states': 'https://r2.thesportsdb.com/images/media/team/badge/6t29a81534960378.png',
};

export function FootballBadge({
  url,
  name,
  size = 32,
  className = '',
}: FootballBadgeProps) {
  const [failedUrls, setFailedUrls] = useState<string[]>([]);

  const cleanName = (name || '').toLowerCase().trim();
  const fallbackUrl = FALLBACK_TEAM_BADGES[cleanName];
  const resolvedUrl = url && !failedUrls.includes(url)
    ? url
    : fallbackUrl && !failedUrls.includes(fallbackUrl)
      ? fallbackUrl
      : null;

  const initials = name
    ? name
        .split(' ')
        .map((w) => w[0])
        .filter(Boolean)
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'FC';

  if (!resolvedUrl) {
    return (
      <div
        className={`inline-flex items-center justify-center font-bold text-xs rounded-full shadow-inner border border-surface1/60 bg-surface0 text-text shrink-0 ${className}`}
        style={{ width: size, height: size }}
        title={name}
      >
        <span style={{ fontSize: Math.max(10, Math.floor(size * 0.38)) }}>
          {initials}
        </span>
      </div>
    );
  }

  return (
    <Image
      src={resolvedUrl}
      alt={name}
      width={size}
      height={size}
      onError={() => setFailedUrls((current) => (
        current.includes(resolvedUrl) ? current : [...current, resolvedUrl]
      ))}
      unoptimized
      className={`object-contain shrink-0 transition-transform duration-200 hover:scale-110 ${className}`}
      style={{ width: size, height: size, maxWidth: size, maxHeight: size }}
    />
  );
}

interface CompetitionBadgeProps {
  code?: string;
  name: string;
  badge_url?: string | null;
  size?: number;
  className?: string;
}

export function CompetitionBadge({
  code,
  name,
  badge_url,
  size = 36,
  className = '',
}: CompetitionBadgeProps) {
  const [error, setError] = useState(false);

  if (!badge_url || error) {
    const isTournament = code === 'UCL' || code === 'CWC' || code === 'WC';
    return (
      <div
        className={`inline-flex items-center justify-center rounded-xl bg-surface0 border border-surface1 shadow-sm text-blue shrink-0 ${className}`}
        style={{ width: size, height: size }}
        title={name}
      >
        {isTournament ? (
          <Trophy size={Math.floor(size * 0.55)} className="text-yellow" />
        ) : (
          <Shield size={Math.floor(size * 0.55)} className="text-sapphire" />
        )}
      </div>
    );
  }

  return (
    <Image
      src={badge_url}
      alt={name}
      width={size}
      height={size}
      onError={() => setError(true)}
      unoptimized
      className={`object-contain shrink-0 drop-shadow-md transition-transform duration-200 hover:scale-105 ${className}`}
      style={{ width: size, height: size, maxWidth: size, maxHeight: size }}
    />
  );
}

interface PlayerAvatarProps {
  image_url?: string | null;
  name: string;
  size?: number;
  className?: string;
  ring?: boolean;
}

export function PlayerAvatar({
  image_url,
  name,
  size = 56,
  className = '',
  ring = true,
}: PlayerAvatarProps) {
  const [error, setError] = useState(false);

  const initials = name
    ? name
        .split(' ')
        .map((w) => w[0])
        .filter(Boolean)
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'PL';

  const ringClasses = ring
    ? 'ring-2 ring-blue/50 dark:ring-blue/60 ring-offset-2 ring-offset-surface0 shadow-md'
    : 'border border-surface1/80 shadow-sm';

  if (!image_url || error) {
    return (
      <div
        className={`inline-flex items-center justify-center rounded-full bg-gradient-to-br from-blue/20 via-sapphire/15 to-mauve/20 text-blue font-bold shrink-0 ${ringClasses} ${className}`}
        style={{ width: size, height: size }}
        title={name}
      >
        {size >= 40 ? (
          <span style={{ fontSize: Math.max(11, Math.floor(size * 0.36)) }}>
            {initials}
          </span>
        ) : (
          <User size={Math.floor(size * 0.5)} className="text-blue" />
        )}
      </div>
    );
  }

  return (
    <Image
      src={image_url}
      alt={name}
      width={size}
      height={size}
      onError={() => setError(true)}
      unoptimized
      className={`rounded-full object-cover bg-surface1/30 shrink-0 transition-all duration-200 hover:scale-105 hover:ring-sapphire ${ringClasses} ${className}`}
      style={{ width: size, height: size, minWidth: size, minHeight: size }}
    />
  );
}
