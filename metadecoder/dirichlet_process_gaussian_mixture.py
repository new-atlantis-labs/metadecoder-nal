from datetime import datetime
from math import ceil

import numpy
from numpy.linalg import inv, slogdet
from scipy.special import digamma, logsumexp
from sklearn.cluster import KMeans


class DPGMM:


    def __init__(self, components, min_component_weight, x, x_weight, random_number, max_iterations = 500, tolerance = 1e-3):
        self.__max_components = components
        self.__min_component_weight = min_component_weight
        self.__x = x # pca(kmer frequency) + coverage #
        self.__x_weight = x_weight
        self.__random_number = random_number
        self.__beta_prior_alpha = 1.0
        self.__gaussian_prior_kappa = 1e-3
        self.__max_iterations = max_iterations
        self.__tolerance = tolerance


    def __initialize_gaussian_prior_mu(self):
        self.__gaussian_prior_mu = numpy.average(self.__x, axis = 0, weights = self.__x_weight)


    def __initialize_wishart_prior_df(self):
        self.__wishart_prior_df = self.__features


    def __initialize_wishart_prior_psi(self):
        x_minus_gaussian_prior_mu = self.__x - self.__gaussian_prior_mu
        self.__wishart_prior_psi = x_minus_gaussian_prior_mu.T @ x_minus_gaussian_prior_mu / (self.__samples - 1.)


    def __initialize_multinomial_fai(self):
        self.__multinomial_fai = numpy.zeros(shape = (self.__samples, self.__components), dtype = numpy.float64)
        kmeans = KMeans(n_clusters = min(self.__components, self.__samples), n_init = 2, random_state = self.__random_number)
        kmeans_labels = kmeans.fit_predict((self.__x - self.__gaussian_prior_mu) / (numpy.sqrt(numpy.diag(self.__wishart_prior_psi)) + numpy.finfo(numpy.float64).eps))
        for label in range(self.__components):
            self.__multinomial_fai[kmeans_labels == label, label] = 1.0


    def __initialize_component_weight(self):
        '''
        self.__component_weight: (self.__components,)
        '''
        pass


    def __initialize_beta_gamma(self):
        '''
        self.__beta_gamma: (self.__components, 2)
        '''
        pass


    def __initialize_gaussian_kappa(self):
        '''
        self.__gaussian_kappa: (self.__components,)
        '''
        pass


    def __initialize_gaussian_mu(self):
        '''
        self.__gaussian_mu: (self.__components, self.__features)
        self.__gaussian_mu_outer_product: (self.__components, self.__features, self.__features)
        '''
        pass


    def __initialize_wishart_df(self):
        '''
        self.__wishart_df: (self.__components,)
        '''
        pass


    def __initialize_wishart_psi(self):
        '''
        self.__wishart_psi: (self.__components, self.__features, self.__features)
        self.__wishart_psi_inverse: (self.__components, self.__features, self.__features)
        self.__wishart_psi_log_determinant: (self.__components,)
        '''
        pass


    def __update_beta_gamma(self):
        self.__beta_gamma = numpy.empty(shape = (self.__components, 2), dtype = numpy.float64)
        self.__beta_gamma[ : , 0] = 1. + self.__component_weight
        self.__beta_gamma[ : , 1] = self.__beta_prior_alpha + numpy.hstack((numpy.cumsum(self.__component_weight[ : 0 : -1])[ : : -1], 0))


    def __update_gaussian_kappa(self):
        self.__gaussian_kappa = self.__gaussian_prior_kappa + self.__component_weight


    def __update_gaussian_mu(self):
        self.__gaussian_mu = (self.__gaussian_prior_kappa * self.__gaussian_prior_mu + self.__multinomial_fai.T * self.__x_weight @ self.__x) / self.__gaussian_kappa.reshape(self.__components, 1)


    def __update_wishart_df(self):
        self.__wishart_df = self.__wishart_prior_df + self.__component_weight


    def __update_wishart_psi(self):
        '''
        self.__wishart_psi = numpy.empty(shape = (self.__components, self.__features, self.__features), dtype = numpy.float64)
        self.__wishart_psi[ : ] = self.__gaussian_prior_kappa * self.__gaussian_prior_mu_outer_product + self.__wishart_prior_psi
        for component in range(self.__components):
            self.__wishart_psi[component] += (
                numpy.sum(self.__x_outer_product * (self.__multinomial_fai[ : , component] * self.__x_weight).reshape(self.__samples, 1, 1), axis = 0)
                - self.__gaussian_kappa[component] * self.__gaussian_mu_outer_product[component]
            )
        self.__wishart_psi_inverse = inv(self.__wishart_psi)
        self.__wishart_psi_log_determinant = slogdet(self.__wishart_psi)[1]
        '''
        self.__wishart_psi = numpy.empty(shape = (self.__components, self.__features, self.__features), dtype = numpy.float64)
        for component in range(self.__components):
            component_mu_minus_gaussian_prior_mu = self.__component_mu[component] - self.__gaussian_prior_mu
            self.__wishart_psi[component] = (
                self.__wishart_prior_psi
                + self.__component_weight[component] * (self.__component_sigma[component] + self.__gaussian_prior_kappa / self.__gaussian_kappa[component] * numpy.outer(component_mu_minus_gaussian_prior_mu, component_mu_minus_gaussian_prior_mu))
            )
        self.__wishart_psi_inverse = inv(self.__wishart_psi)
        self.__wishart_psi_log_determinant = slogdet(self.__wishart_psi)[1]


    def __update_multinomial_fai(self):
        '''
        self.__multinomial_fai = numpy.empty(shape = (self.__samples, self.__components), dtype = numpy.float64)
        digamma_gamma = digamma(self.__beta_gamma) # digamma(γ1), digamma(γ2)
        self.__multinomial_fai[ : ] = (
            # component_weight > #
            # = E[ln(v_t)] + E{i:1->t-1}[ln(1-v_i)] #
            # = digamma(γ_t,1) - digamma(γ_t,1 + γ_t,2) + ∑{i:1->t-1}(digamma(γ_i,2) - digamma(γ_i,1 + γ_i,2)) #
            # = digamma(γ_t,1) + ∑{i:1->t-1}(digamma(γ_i,2)) - ∑{i:1->t}(digamma(γ_i,1 + γ_i,2)) #
            digamma_gamma[ : , 0]
            + numpy.hstack((0, numpy.cumsum(digamma_gamma[ : -1, 1])))
            - numpy.cumsum(digamma(numpy.sum(self.__beta_gamma, axis = 1)))
            # < component_weight #
            + 0.5 * (
                # ψd(x) = ∑{i: 1 -> d} ψ((df - (i - 1)) / 2) #
                + numpy.sum(digamma((self.__wishart_df - numpy.arange(self.__features).reshape(-1, 1)) / 2.), axis = 0)
                # d * ln2 #
                + self.__features * numpy.log(2.)
                # ln(ψ) #
                - self.__wishart_psi_log_determinant
                # d / kappa #
                - self.__features / self.__gaussian_kappa
                # vt(µ.Tψ^-1µ) #
                - self.__wishart_df * numpy.trace(self.__gaussian_mu_outer_product @ self.__wishart_psi_inverse, axis1 = 1, axis2 = 2)
            )
        )
        for component in range(self.__components):
            # vec(vψ-1)vec(xx.T) + inner(vψ-1mu0,xn) #
            self.__multinomial_fai[ : , component] += (
                self.__wishart_df[component] * (
                    - 0.5 * numpy.trace(self.__x_outer_product @ self.__wishart_psi_inverse[component], axis1 = 1, axis2 = 2)
                    + (self.__x @ (self.__wishart_psi_inverse[component] @ self.__gaussian_mu[component].reshape(self.__features, 1))).flat
                )
            )
        self.__multinomial_fai = numpy.exp(self.__multinomial_fai - logsumexp(self.__multinomial_fai, axis = 1, keepdims = True))
        '''
        digamma_gamma = digamma(self.__beta_gamma) # digamma(γ1), digamma(γ2)
        self.__multinomial_fai[ : ] = (
            # component_weight > #
            # = E[ln(v_t)] + E{i:1->t-1}[ln(1-v_i)] #
            # = digamma(γ_t,1) - digamma(γ_t,1 + γ_t,2) + ∑{i:1->t-1}(digamma(γ_i,2) - digamma(γ_i,1 + γ_i,2)) #
            # = digamma(γ_t,1) + ∑{i:1->t-1}(digamma(γ_i,2)) - ∑{i:1->t}(digamma(γ_i,1 + γ_i,2)) #
            digamma_gamma[ : , 0]
            + numpy.hstack((0, numpy.cumsum(digamma_gamma[ : -1, 1])))
            - numpy.cumsum(digamma(numpy.sum(self.__beta_gamma, axis = 1)))
            # < component_weight #
            + 0.5 * (
                # ψd(x) = ∑{i: 1 -> d} ψ((df - (i - 1)) / 2) #
                + numpy.sum(digamma((self.__wishart_df - numpy.arange(self.__features).reshape(-1, 1)) / 2.), axis = 0)
                # d * ln2 #
                # + self.__features * numpy.log(2.)
                # ln(|ψ|) #
                - self.__wishart_psi_log_determinant
                # d / kappa #
                - self.__features / self.__gaussian_kappa
            )
        )
        for component in range(self.__components):
            x_minus_gaussian_mu = self.__x - self.__gaussian_mu[component] # (self.__samples, self.__features) #
            self.__multinomial_fai[: , component] += (
                - 0.5 * self.__wishart_df[component] * numpy.sum(x_minus_gaussian_mu @ self.__wishart_psi_inverse[component] * x_minus_gaussian_mu, axis = 1)
            )
        self.__multinomial_fai = numpy.exp(self.__multinomial_fai - logsumexp(self.__multinomial_fai, axis = 1, keepdims = True))


    def __shrink_multinomial_fai(self):
        components = numpy.sum(self.__component_weight < self.__min_component_weight)
        components = numpy.argsort(self.__component_weight)[min(ceil(components * 0.9), self.__components - 1) : ]
        self.__multinomial_fai = self.__multinomial_fai[ : , numpy.sort(components)]
        self.__multinomial_fai /= (numpy.sum(self.__multinomial_fai, axis = 1, keepdims = True) + numpy.finfo(numpy.float64).eps)
        self.__components = components.shape[0]


    def __update_component_weight(self):
        self.__component_weight = self.__x_weight @ self.__multinomial_fai + numpy.finfo(numpy.float64).eps


    def __update_component_mu(self):
        self.__component_mu = (self.__multinomial_fai.T * self.__x_weight) @ self.__x / self.__component_weight.reshape(self.__components, 1)


    def __update_component_sigma(self):
        self.__component_sigma = numpy.empty(shape = (self.__components, self.__features, self.__features), dtype = numpy.float64)
        for component in range(self.__components):
            x_minus_component_mu = self.__x - self.__component_mu[component] # (self.__samples, self.__features) #
            self.__component_sigma[component] = (self.__multinomial_fai[:, component] * self.__x_weight * x_minus_component_mu.T) @ x_minus_component_mu / self.__component_weight[component]
            self.__component_sigma[component][numpy.diag_indices(self.__features)] += 1e-6


    def __is_convergence(self):
        return numpy.mean(numpy.sqrt(numpy.sum(numpy.square(self.multinomial_fai - self.__multinomial_fai), axis = 1))) < self.__tolerance


    def main(self):
        self.__samples, self.__features = self.__x.shape
        self.__initialize_gaussian_prior_mu() # mean of x
        self.__initialize_wishart_prior_df() # features
        self.__initialize_wishart_prior_psi() # cov of weighted x
        self.__components = self.__max_components # The current number of components is from "max_components" to "min_component".
        iterations = 0
        iterations_ = 0
        self.__initialize_multinomial_fai()
        self.__update_component_weight()
        while True:

            # m step #
            self.__update_component_mu()
            self.__update_component_sigma()
            self.__update_beta_gamma()
            self.__update_gaussian_kappa()
            self.__update_gaussian_mu()
            self.__update_wishart_df()
            self.__update_wishart_psi()

            # e step
            self.multinomial_fai = numpy.copy(self.__multinomial_fai)
            self.__update_multinomial_fai()
            self.__update_component_weight()

            iterations += 1
            iterations_ += 1
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '->', 'DPGMM: {0} iterations have been finished ({1} components).'.format(iterations, self.__components), flush = True)
            if (iterations == self.__max_iterations) or (self.__components == 1):
                break
            elif numpy.min(self.__component_weight) >= self.__min_component_weight:
                if self.__is_convergence() or (iterations_ >= 100):
                    break
            elif (iterations >= 20) and (not (iterations % 10)):
                self.__shrink_multinomial_fai()
                self.__update_component_weight()
                iterations_ = 0