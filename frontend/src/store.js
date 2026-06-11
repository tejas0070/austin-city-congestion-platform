import { createStore, combineReducers, applyMiddleware, compose } from 'redux';
import keplerGlReducer from '@kepler.gl/reducers';
import { enhanceReduxMiddleware } from '@kepler.gl/reducers';

const reducers = combineReducers({
  keplerGl: keplerGlReducer,
});

const middlewares = enhanceReduxMiddleware([]);

const composeEnhancers =
  (typeof window !== 'undefined' && window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__) || compose;

const store = createStore(
  reducers,
  {},
  composeEnhancers(applyMiddleware(...middlewares))
);

export default store;
