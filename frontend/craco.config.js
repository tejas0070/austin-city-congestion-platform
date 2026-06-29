const path = require('path');

module.exports = {
  webpack: {
    configure: (webpackConfig) => {
      webpackConfig.resolve.fallback = {
        ...webpackConfig.resolve.fallback,
        stream: require.resolve('stream-browserify'),
        buffer: require.resolve('buffer/'),
        crypto: require.resolve('crypto-browserify'),
        path: require.resolve('path-browserify'),
        assert: require.resolve('assert/'),
        url: require.resolve('url/'),
        util: require.resolve('util/'),
        os: require.resolve('os-browserify/browser'),
        fs: false,
        net: false,
        tls: false,
      };

      // kepler.gl runs addDataToMap's dataset creation through react-palm
      // "tasks". The task middleware is installed from @kepler.gl/reducers'
      // copy of react-palm, but CREATE_TABLE_TASK is constructed in
      // @kepler.gl/table's copy. Each @kepler.gl/* package nests its OWN
      // react-palm (there is no hoisted top-level one), so a task created by one
      // copy isn't recognised by the middleware from another. The unrecognised
      // create-table task is then dropped, and kepler raises an intermittent
      // "Failed to create a new dataset due to data verification errors" toast
      // for whichever dataset lost the race (the data itself is always valid).
      // Aliasing react-palm to a single copy makes task identity consistent so
      // every create-table task runs. All @kepler.gl/* peers pin ^3.3.8, so one
      // shared copy is exactly what they expect.
      const reactPalm = path.dirname(
        require.resolve('react-palm/package.json', {
          paths: [path.resolve(__dirname, 'node_modules/@kepler.gl/reducers')],
        })
      );

      // Route all mapbox-gl imports (including kepler.gl internals) through
      // maplibre-gl — avoids Mapbox token requirements entirely.
      webpackConfig.resolve.alias = {
        ...webpackConfig.resolve.alias,
        'mapbox-gl': 'maplibre-gl',
        // Single shared react-palm (see comment above). Matches `react-palm`
        // and its subpaths (`react-palm/tasks`, `react-palm/actions`, …).
        'react-palm': reactPalm,
        // shadcn-style absolute imports: `@/components/ui/...` -> `src/...`.
        // Only matches requests beginning with `@/`, so scoped packages such as
        // `@kepler.gl/*` are unaffected.
        '@': path.resolve(__dirname, 'src'),
      };

      // kepler.gl ships .cjs files; webpack 5 asset modules treat unknown
      // extensions as static files and return a URL string instead of the
      // module exports. The rule must live INSIDE CRA's oneOf block before the
      // catch-all asset rule — pushing to the outer rules array runs too late.
      const oneOfRule = webpackConfig.module.rules.find(
        (r) => Array.isArray(r.oneOf)
      );
      if (!oneOfRule) {
        throw new Error(
          'CRA webpack config no longer has a oneOf rule — update craco.config.js'
        );
      }
      oneOfRule.oneOf.unshift({ test: /\.cjs$/, type: 'javascript/auto' });

      // Prevent "fullySpecified" errors from ESM packages that omit extensions
      webpackConfig.module.rules.push({
        test: /\.m?js$/,
        resolve: { fullySpecified: false },
      });

      return webpackConfig;
    },
  },
};
