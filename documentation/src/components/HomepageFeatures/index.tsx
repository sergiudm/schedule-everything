import React, { JSX } from 'react';
import clsx from 'clsx';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  Svg: React.ComponentType<React.ComponentProps<'svg'>>;
  description: React.ReactNode; // Change JSX.Element to React.ReactNode
};

const FeatureList: FeatureItem[] = [
  {
    title: 'TOML Configuration',
    Svg: require('@site/static/img/undraw_docusaurus_mountain.svg').default,
    description: (
      <>
        Use human-readable TOML files to define your schedules. Version control
        friendly, portable, and no vendor lock-in. Your schedule is code!
      </>
    ),
  },
  {
    title: 'Persistent Reminders',
    Svg: require('@site/static/img/undraw_docusaurus_tree.svg').default,
    description: (
      <>
        Dual alert system with both audible sounds and modal dialogs. Alarms
        repeat until manually dismissed—perfect for staying accountable.
      </>
    ),
  },
  {
    title: 'Smart Weekly Rotation',
    Svg: require('@site/static/img/undraw_docusaurus_react.svg').default,
    description: (
      <>
        Automatically alternates between odd and even week schedules using
        ISO week numbering. Perfect for sprint cycles and alternating routines.
      </>
    ),
  },
  {
    title: 'CLI Integration',
    Svg: require('@site/static/img/undraw_docusaurus_mountain.svg').default,
    description: (
      <>
        Powerful command-line interface for schedule management and task tracking.
        Add, remove, and prioritize tasks with importance levels.
      </>
    ),
  },
  {
    title: 'Task Management',
    Svg: require('@site/static/img/undraw_docusaurus_tree.svg').default,
    description: (
      <>
        Built-in task list with importance levels and smart duplicate handling.
        Tasks persist across sessions and are sorted by priority.
      </>
    ),
  },
  {
    title: 'Auto-start Service',
    Svg: require('@site/static/img/undraw_docusaurus_react.svg').default,
    description: (
      <>
        Runs silently in the background via launchd/systemd. No manual startup
        required—your schedule is always active.
      </>
    ),
  },
];

function Feature({ title, Svg, description }: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): JSX.Element {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
