import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { TrendPoint } from '../../api/types';

interface TrendsChartProps {
  data: TrendPoint[];
}

export const TrendsChart: React.FC<TrendsChartProps> = ({ data }) => {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="purpleGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="greenGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10B981" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272F" vertical={false} />
          <XAxis
            dataKey="date"
            stroke="#71717A"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: '#27272F' }}
            tickFormatter={(val: string) => {
              const parts = val.split('-');
              return parts.length === 3 ? `${parts[1]}/${parts[2]}` : val;
            }}
          />
          <YAxis
            stroke="#71717A"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: '#27272F' }}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#111116',
              border: '1px solid #27272F',
              borderRadius: '12px',
              boxShadow: '0 8px 24px -4px rgba(0,0,0,0.6)',
              fontSize: '12px',
            }}
            labelStyle={{ color: '#F5F5F7', fontWeight: 600, marginBottom: '4px' }}
            itemStyle={{ padding: '2px 0' }}
          />
          <Area
            type="monotone"
            dataKey="incidents_created"
            name="Incidents Ingested"
            stroke="#8B5CF6"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#purpleGradient)"
          />
          <Area
            type="monotone"
            dataKey="incidents_recovered"
            name="Recoveries (all modes)"
            stroke="#10B981"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#greenGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

